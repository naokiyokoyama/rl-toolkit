python tests/test_cmds/ppo/def.py --num-env-steps 1e5 --linear-lr-decay True --lr 0.001 --prefix 'ppo-cartpole-test' --num-steps 32 --num-mini-batch 1 --num-epochs 20 --entropy-coef 0.0 --env-name "CartPole-v1" --num-processes 8 --eval-interval -1 --save-interval -1 --log-smooth-len 1  --env-log-dir ~/tmp 
