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
- on mac, if you use metal, it will be twice as fast towards later trials, but you need to do: `export PYTORCH_ENABLE_MPS_FALLBACK=1`
- do `cd ..` and run `sh scripts/baseline.sh` 