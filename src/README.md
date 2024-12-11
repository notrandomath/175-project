# cs175project
## Set Up Environment
- `conda create -n 175-env python=3.9`
- `conda activate 175-env`
- `conda install poetry`
- `git clone https://github.com/notrandomath/175-project.git && cd cleanrl`
- `which poetry` to get the path to poetry for next commands
- `conda deactivate`

make sure you're in `cleanrl` folder for the next commands:
- `[path to poetry] install`
- `[path to poetry] install -E atari`
- `brew install ffmpeg` on mac or `sudo apt-install ffmpeg` on linux

if planning on running project.ipynb:
- `[path to poetry] install ipykernel` if planning on using to run project.ipynb
- `[path to poetry] run python -m ipykernel install --user --name openai_gym_bros --display-name "Python (openai_gym_bros)"`
- `[path to poetry] add --group dev jupyter`
- `[path to poetry] run jupyter notebook`
## Relevant Files
We modified:
- `cleanrl/dqn_atari.py`
- `cleanrl/ppo_atari.py`
- `cleanrl_utils/evals/ppo_eval.py`

We created:
- entire `scripts/` directory