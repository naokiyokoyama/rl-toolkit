python tests/test_cmds/ddpg/def.py --prefix 'her-test' --num-env-steps 3e6 --env-name "FetchReach-v1" --eval-interval -1 --log-smooth-len 10 --save-interval -1 --lr 0.001 --critic-lr 0.001 --tau 0.05 --warmup-steps 0 --update-every 10 --trans-buffer-size 50000 --batch-size 32 --linear-lr-decay False --max-grad-norm -1 --noise-std 0.25 --noise-type gaussian
