from collections import defaultdict
from functools import partial

import numpy as np
import rlf.algos.utils as autils
import rlf.rl.utils as rutils
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from rlf.algos.il.base_irl import BaseIRLAlgo
from rlf.algos.nested_algo import NestedAlgo
from rlf.algos.on_policy.ppo import PPO
from rlf.args import str2bool
from rlf.baselines.common.running_mean_std import RunningMeanStd
from rlf.exp_mgr.viz_utils import append_text_to_image
from rlf.rl.model import ConcatLayer, InjectNet
from torch.nn.utils import spectral_norm


def get_default_discrim(hidden_dim: int) -> nn.Module:
    """
    Takes as input the hidden dimension passed via the discriminator command line argument.
    Returns the discriminator network HEAD. The base layer to encode the input is separately created.
    """
    layers = [
        nn.Linear(hidden_dim, hidden_dim),
        nn.Tanh(),
        nn.Linear(hidden_dim, 1),
    ]

    return nn.Sequential(*layers)


class GAIL(NestedAlgo):
    def __init__(self, agent_updater=PPO(), get_discrim=None, exp_generator=None):
        super().__init__(
            [GailDiscrim(get_discrim, exp_generator=exp_generator), agent_updater], 1
        )


class GailDiscrim(BaseIRLAlgo):
    def __init__(self, get_discrim=None, exp_generator=None):
        super().__init__(exp_generator=exp_generator)
        if get_discrim is None:
            get_discrim = get_default_discrim
        self.get_discrim = get_discrim

    def _create_discrim(self):
        ob_shape = rutils.get_obs_shape(self.policy.obs_space)
        ac_dim = rutils.get_ac_dim(self.action_space)
        base_net = self.policy.get_base_net_fn(ob_shape)
        discrim = self.get_discrim(self.args.gail_disc_hidden_dim)
        discrim_head = InjectNet(
            base_net.net,
            discrim,
            base_net.output_shape[0],
            self.args.gail_disc_hidden_dim,
            ac_dim,
            self.args.action_input,
        )

        return discrim_head.to(self.args.device)

    def init(self, policy, args):
        super().init(policy, args)
        self.action_space = self.policy.action_space

        self.discrim_net: nn.Module = self._create_discrim()

        if self.args.use_spectral_norm:
            for name, module in self.discrim_net.named_modules():
                # Only applies the spectral transformation to the high-level
                # modules and goes into the sequential modules and applies to
                # each element.
                if name == "" or "." in name:
                    continue
                if isinstance(module, nn.Sequential):
                    new_layers = []
                    for i in range(len(module)):
                        layer = module[i]
                        if isinstance(layer, nn.Linear):
                            layer = spectral_norm(layer)
                        new_layers.append(layer)
                    setattr(self.discrim_net, name, nn.Sequential(*new_layers))
                elif isinstance(module, nn.Linear):
                    setattr(self.discrim_net, name, spectral_norm(layer))

        self.returns = None
        self.ret_rms = RunningMeanStd(shape=())

        self.opt = optim.Adam(self.discrim_net.parameters(), lr=self.args.disc_lr)

    def _get_sampler(self, storage):
        if self.args.gail_max_agent_batch_size:
            use_batch_size = len(storage) // len(self.expert_train_loader)
            if use_batch_size == 0:
                raise ValueError("Maximizing GAIL agent sampler does not work")
        else:
            use_batch_size = self.expert_train_loader.batch_size

        agent_experience = storage.get_generator(
            mini_batch_size=use_batch_size,
            from_recent=self.args.off_policy_recent,
            num_samples=self.args.off_policy_count,
        )
        return self.expert_train_loader, agent_experience

    def _trans_batches(self, expert_batch, agent_batch):
        return expert_batch, agent_batch

    def get_env_settings(self, args):
        settings = super().get_env_settings(args)
        if not args.gail_state_norm:
            settings.ret_raw_obs = True
        settings.mod_render_frames_fn = self.mod_render_frames
        return settings

    def mod_render_frames(
        self, frame, env_cur_obs, env_cur_action, env_cur_reward, env_next_obs, **kwargs
    ):
        use_cur_obs = rutils.get_def_obs(env_cur_obs)
        use_cur_obs = torch.FloatTensor(use_cur_obs).unsqueeze(0).to(self.args.device)

        if env_cur_action is not None:
            use_action = (
                torch.FloatTensor(env_cur_action).unsqueeze(0).to(self.args.device)
            )
            disc_val = self._compute_disc_val(use_cur_obs, use_action).item()
        else:
            disc_val = 0.0

        frame = append_text_to_image(
            frame,
            [
                "Discrim: %.3f" % disc_val,
                "Reward: %.3f"
                % (env_cur_reward if env_cur_reward is not None else 0.0),
            ],
        )
        return frame

    def _norm_expert_state(self, state, obsfilt):
        if not self.args.gail_state_norm:
            return state
        state = state.cpu().numpy()

        if obsfilt is not None:
            state = obsfilt(state, update=False)
        state = torch.tensor(state).to(self.args.device)
        return state

    def _trans_agent_state(self, state, other_state=None):
        if not self.args.gail_state_norm:
            if other_state is None:
                return state["raw_obs"]
            return other_state["raw_obs"]
        return rutils.get_def_obs(state)

    def _compute_discrim_loss(self, agent_batch, expert_batch, obsfilt):
        expert_actions = expert_batch["actions"].to(self.args.device)
        expert_actions = self._adjust_action(expert_actions)
        expert_states = self._norm_expert_state(expert_batch["state"], obsfilt)

        agent_states = self._trans_agent_state(
            agent_batch["state"],
            agent_batch["other_state"] if "other_state" in agent_batch else None,
        )
        agent_actions = agent_batch["action"]

        agent_actions = rutils.get_ac_repr(self.action_space, agent_actions)
        expert_actions = rutils.get_ac_repr(self.action_space, expert_actions)

        expert_d = self._compute_disc_val(expert_states, expert_actions)
        agent_d = self._compute_disc_val(agent_states, agent_actions)

        if self.args.disc_grad_pen > 0:
            grad_pen = self.compute_pen(
                expert_states, expert_actions, agent_states, agent_actions
            )
        else:
            grad_pen = 0.0

        return expert_d, agent_d, grad_pen

    def compute_pen(self, expert_states, expert_actions, agent_states, agent_actions):
        grad_pen = self.args.disc_grad_pen * autils.wass_grad_pen(
            expert_states,
            expert_actions,
            agent_states,
            agent_actions,
            self.args.action_input,
            self._compute_disc_val,
        )
        return grad_pen

    def _compute_disc_val(self, state, action):
        return self.discrim_net(state, action)

    def _compute_expert_loss(self, expert_d, expert_batch):
        return F.binary_cross_entropy_with_logits(
            expert_d, torch.ones(expert_d.shape).to(self.args.device)
        )

    def _compute_agent_loss(self, agent_d, agent_batch):
        return F.binary_cross_entropy_with_logits(
            agent_d, torch.zeros(agent_d.shape).to(self.args.device)
        )

    def _update_reward_func(self, storage):
        if self.args.freeze_reward:
            return {}
        self.discrim_net.train()

        log_vals = defaultdict(lambda: 0)
        obsfilt = self.get_env_ob_filt()

        n = 0
        expert_sampler, agent_sampler = self._get_sampler(storage)
        if agent_sampler is None:
            # algo requested not to update this step
            return {}

        for epoch_i in range(self.args.n_gail_epochs):
            for expert_batch, agent_batch in zip(expert_sampler, agent_sampler):
                expert_batch, agent_batch = self._trans_batches(
                    expert_batch, agent_batch
                )
                n += 1
                expert_d, agent_d, grad_pen = self._compute_discrim_loss(
                    agent_batch, expert_batch, obsfilt
                )
                expert_loss = self._compute_expert_loss(expert_d, expert_batch)
                agent_loss = self._compute_agent_loss(agent_d, agent_batch)

                discrim_loss = expert_loss + agent_loss

                if self.args.disc_grad_pen != 0.0:
                    log_vals["grad_pen"] += grad_pen.item()
                    total_loss = discrim_loss + grad_pen
                else:
                    total_loss = discrim_loss

                self.opt.zero_grad()
                total_loss.backward()
                self.opt.step()

                log_vals["discrim_loss"] += discrim_loss.item()
                log_vals["expert_loss"] += expert_loss.item()
                log_vals["agent_loss"] += agent_loss.item()

        for k in log_vals:
            log_vals[k] /= n

        return log_vals

    def _compute_discrim_reward(self, state, next_state, action, mask, add_inputs):
        action = rutils.get_ac_repr(self.action_space, action)
        d_val = self._compute_disc_val(state, action)
        s = torch.sigmoid(d_val)
        eps = 1e-20
        if self.args.reward_type == "airl":
            reward = (s + eps).log() - (1 - s + eps).log()
        elif self.args.reward_type == "gail":
            reward = (s + eps).log()
        elif self.args.reward_type == "raw":
            reward = d_val
        else:
            raise ValueError(f"Unrecognized reward type {self.args.reward_type}")
        return reward

    def get_viz_reward(self, state, next_state, action, mask, add_info):
        return self._get_reward(state, next_state, action, mask, add_info)[0]

    def _get_reward(self, state, next_state, action, mask, add_inputs):
        with torch.no_grad():
            self.discrim_net.eval()
            reward = self._compute_discrim_reward(
                state, next_state, action, mask, add_inputs
            )

            if self.args.gail_reward_norm:
                if self.returns is None:
                    self.returns = reward.clone()

                self.returns = self.returns * mask * self.args.gamma + reward
                self.ret_rms.update(self.returns.cpu().numpy())

                return reward / np.sqrt(self.ret_rms.var[0] + 1e-8), {}
            else:
                return reward, {}

    def get_add_args(self, parser):
        super().get_add_args(parser)
        #########################################
        # Overrides

        #########################################
        # New args
        parser.add_argument("--action-input", type=str2bool, default=False)
        parser.add_argument("--use-spectral-norm", type=str2bool, default=False)
        parser.add_argument("--gail-reward-norm", type=str2bool, default=False)
        parser.add_argument("--gail-state-norm", type=str2bool, default=True)
        parser.add_argument(
            "--gail-disc-hidden-dim",
            type=int,
            default=64,
            help="""
                The hidden dimension passed to the discriminator neural network creation function.
                """,
        )
        parser.add_argument("--disc-lr", type=float, default=0.0001)
        parser.add_argument("--disc-grad-pen", type=float, default=0.0)
        parser.add_argument("--n-gail-epochs", type=int, default=1)
        parser.add_argument(
            "--reward-type",
            type=str,
            default="airl",
            help="""
                One of [airl, raw, gail]. Changes the reward computation. Does
                not change training.
                """,
        )
        parser.add_argument(
            "--gail-max-agent-batch-size",
            type=str2bool,
            default=False,
            help="""
                If true, this will not use traj-batch-size as the batch size of
                agent experience when updating the discriminator and instead
                use the largest possible batch size such that the number of
                batches equals the number of batches from the expert data
                sampler. This is helpful for when there are not many expert
                demonstrations.
                """,
        )
        parser.add_argument("--off-policy-recent", type=str2bool, default=True)
        parser.add_argument("--off-policy-count", type=int, default=2048)

        parser.add_argument(
            "--freeze-reward",
            type=str2bool,
            default=False,
            help="""
                If true, the discriminator is not updated.
            """,
        )

    def load_resume(self, checkpointer):
        super().load_resume(checkpointer)
        self.opt.load_state_dict(checkpointer.get_key("gail_disc_opt"))

    def load(self, checkpointer):
        super().load(checkpointer)
        self.discrim_net.load_state_dict(checkpointer.get_key("gail_disc"))

    def save(self, checkpointer):
        super().save(checkpointer)
        checkpointer.save_key("gail_disc_opt", self.opt.state_dict())
        checkpointer.save_key("gail_disc", self.discrim_net.state_dict())
