# RL Toolkit (RLT)

# Still a work in progress.

A framework to quickly and flexibly implement RL algorithms. Easily implement
your own RL algorithms. Have control over the key features and only focus on
the important parts. You can do all of these things without touching any of the code!
- Custom policies. 
- Custom update functions.
- Configurable replay buffer or trajectory storage. Control how you collect
  agent experience. 
- Custom loggers. Default integration for TensorBoard and W&B.
- Define environment wrappers. Use this to log custom environment statistics,
  define and pass command line arguments, and add wrappers. 
- Environment multi-processing.
- Integration with Ray auto hyperparameter tuning. 
- Automated experiment runner. Includes command templates, multiple seed
  runner, and tmux integration. 
- Auto figure creation.

## Algorithms
- On policy:
  - PPO
  - REINFORCE
  - A2C 
- Off policy:
  - DQN
  - DDPG
- Imitation learning:
  - Behavioral cloning
  - GAIL
  - BCO

See learning curves for these algorithms [below](https://github.com/ASzot/rl-toolkit#benchmarks)

Many more to be added soon! 

## Installation
Requires Python 3.7. With conda: 

- `conda create -n rlf python=3.7`
- `source activate rlf`
- `pip install -r requirements.txt`.

Some additional environments you can install:
- `dm_control`: 
  - `pip install dm_control` 
  - `export MJLIB_PATH=/home/aszot/.mujoco/mujoco200/bin/libmujoco200.so` (or
    wherever your MuJoCo install is).
  - To run these environments use format `--env-name dm.domain.task`
- `robosuite`
  - `pip install robosuite`
- `gym-minigrid`
  - `pip install install gym-minigrid`

## Run Tests
The most important principle in this code is **working RL algorithms**.
Automated benchmarking scripts are included under `tests/test_cmds` so you can
be sure the code is working. For example, to run the PPO benchmark on Hopper-v3
with 5 seeds, run: `python -m rlf --cfg tests/config.yaml --cmd ppo/hopper  --seed
"31,41,51,61,71"  --sess-id 0`.

## Experiment Runner
Easily run templated commands. Start by defining a `.cmd` file. 
- Send to new tmux pane. 
- Easily run and manage long complicated commands. 
- Add additional arguments to specified command. 
- Specify which GPU to use via a flag. 
- Choose to log to W&B. 

TODO

## Custom Environments
Several keys in the info dictionary are specially treated. 
* `final_obs` if returned when the episode finishes, this is treated as the
  final observation seen before the reset. Note that the agent never acts in
  this state. Having access to this can be useful when viewing the entire
  trajectory of the agent. 
* `raw_obs` if the alg_setting `ret_raw_obs` is returned, then the VecNormalize
  environment will pass the environment observation before any normalization in
  the `raw_obs` field. 

Also included are some common 3rd party RL environments.
* `BitFlip-v0`

# Benchmarks
### Hopper-v3
Commit: `570d8c8d024cb86266610e72c5431ef17253c067`

- PPO: `py -m rlf --cmd ppo/hopper --cd 0 --cfg ./tests/config.yaml --seed "31,41,51" --sess-id 0 --cuda False` 

![Hopper-v3](https://github.com/ASzot/rl-toolkit/blob/master/bench_plots/hopper.png)

### Pendulum-v0
Commit: `5c051769088b6582b0b31db9a145738a9ed68565`
- DDPG: `py -m rlf --cmd ddpg/pendulum --cd 0 --cfg ./tests/config.yaml --seed "31,41" --sess-id 0 --cuda False` 
![Pendulum-v0](https://github.com/ASzot/rl-toolkit/blob/master/bench_plots/pendulum.png)

### BitFlip-v0
Commit: `95bb3a7d0bf1945e414a0e77de8a749bd79dc554`
- HER: `py -m rlf --cmd her/bit_flip --cfg ./tests/config.yaml --cuda False --sess-id 0`
![BitFlip-v0]()
