#!/bin/bash

# Set common variables
env="SpaceInvadersNoFrameskip-v4"
path_to_poetry="/home/omar/miniconda3/envs/175-env/bin/poetry"

# Define function to run python command
run_python_command () {
    $path_to_poetry run python cleanrl/dqn_atari.py \
    --exp_name $1 \
    --env-id $env \
    --capture_video \
    --buffer_size 100000 \
    --save_model \
    --total_timesteps 2000000 \
    --track \
    --prune \
    --prune_method "random" \
    --prune_amount $2
}

# echo "Starting Baseline"
# echo run_python_command
# run_python_command "Baseline" 0
# echo "Finished Baseline"

echo "Starting R 0.05"
echo run_python_command
run_python_command "R_0.05" 0.05
echo "Finished R 0.01"

echo "Starting R 0.1"
echo run_python_command
run_python_command "R_0.1" 0.1
echo "Finished R 0.1"

echo "Starting R 0.3"
echo run_python_command
run_python_command "R_0.3" 0.3
echo "Finished R 0.3"

echo "Starting R 0.5"
echo run_python_command
run_python_command "R_0.5" 0.5
echo "Finished R 0.5"

echo "Starting R 0.8"
echo run_python_command
run_python_command "R_0.8" 0.8
echo "Finished R 0.8"