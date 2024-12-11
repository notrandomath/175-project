#!/bin/bash

# Set common variables
env="SpaceInvadersNoFrameskip-v4"
path_to_poetry="/home/omar/miniconda3/envs/175-env/bin/poetry"

# Define function to run python command
run_python_command () {
    $path_to_poetry run python cleanrl/ppo_atari.py \
    --exp_name $1 \
    --env-id $env \
    --capture_video \
    --total_timesteps 10000 \
    --track \
    --prune \
    --prune_amount $2 \
    --prune_method "random" \
    --save_model
}

echo "Starting L1 0.1"
echo run_python_command
run_python_command "ppo_sanity"  0.1
echo "Finished L1 0.1"