#!/bin/bash

# Set common variables
env="SpaceInvadersNoFrameskip-v4"
path_to_poetry="/home/omar/miniconda3/envs/175-env/bin/poetry"

# Define function to run python command
run_python_command () {
    $path_to_poetry run python cleanrl/dqn_atari.py \
    --env-id $env \
    --capture_video \
    --buffer_size 100000 \
    --save_model \
    --track
}

echo "Creating baseline model"
echo run_python_command
run_python_command
echo "Finished creating baseline model"