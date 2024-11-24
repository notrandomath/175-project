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
    --total_timesteps 2000000 \
    --track \
    --prune \
    --prune_amount $2 \
    --prune_method "random" \
    --save_model
}

echo "Starting R 0.1"
echo run_python_command
run_python_command "ppo_R_0.1" 0.1
echo "Finished R 0.1"

echo "Starting R 0.3"
echo run_python_command
run_python_command "ppo_R_0.3" 0.3
echo "Finished R 0.3"

echo "Starting R 0.5"
echo run_python_command
run_python_command "ppo_R_0.5" 0.5
echo "Finished R 0.5"