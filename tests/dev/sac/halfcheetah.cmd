python tests/dev/sac/main.py --prefix 'sac' --env-name AntPyBulletEnv-v0 --save-interval -1 --normalize-env False --init-temperature 0.1 --alpha-lr 1e-4  --lr 1e-4 --critic-lr 1e-4 --actor-update-freq 1 --tau 0.005 --critic-update-freq 2 --batch-size 1024 --num-env-steps 1e6 --trans-buffer-size 1e6 --log-std-bounds="-5,2" --eval-num-processes 1 --max-grad-norm -1
