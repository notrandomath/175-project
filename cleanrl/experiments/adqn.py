# https://github.com/facebookresearch/torchbeast/blob/master/torchbeast/core/environment.py

import numpy as np
from collections import deque
import gym
from gym import spaces
import cv2
cv2.ocl.setUseOpenCL(False)


class NoopResetEnv(gym.Wrapper):
    def __init__(self, env, noop_max=30):
        """Sample initial states by taking random number of no-ops on reset.
        No-op is assumed to be action 0.
        """
        gym.Wrapper.__init__(self, env)
        self.noop_max = noop_max
        self.override_num_noops = None
        self.noop_action = 0
        assert env.unwrapped.get_action_meanings()[0] == 'NOOP'

    def reset(self, **kwargs):
        """ Do no-op action for a number of steps in [1, noop_max]."""
        self.env.reset(**kwargs)
        if self.override_num_noops is not None:
            noops = self.override_num_noops
        else:
            noops = self.unwrapped.np_random.randint(1, self.noop_max + 1) #pylint: disable=E1101
        assert noops > 0
        obs = None
        for _ in range(noops):
            obs, _, done, _ = self.env.step(self.noop_action)
            if done:
                obs = self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        return self.env.step(ac)

class FireResetEnv(gym.Wrapper):
    def __init__(self, env):
        """Take action on reset for environments that are fixed until firing."""
        gym.Wrapper.__init__(self, env)
        assert env.unwrapped.get_action_meanings()[1] == 'FIRE'
        assert len(env.unwrapped.get_action_meanings()) >= 3

    def reset(self, **kwargs):
        self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(1)
        if done:
            self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(2)
        if done:
            self.env.reset(**kwargs)
        return obs

    def step(self, ac):
        return self.env.step(ac)

class EpisodicLifeEnv(gym.Wrapper):
    def __init__(self, env):
        """Make end-of-life == end-of-episode, but only reset on true game over.
        Done by DeepMind for the DQN and co. since it helps value estimation.
        """
        gym.Wrapper.__init__(self, env)
        self.lives = 0
        self.was_real_done  = True

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        self.was_real_done = done
        # check current lives, make loss of life terminal,
        # then update lives to handle bonus lives
        lives = self.env.unwrapped.ale.lives()
        if lives < self.lives and lives > 0:
            # for Qbert sometimes we stay in lives == 0 condition for a few frames
            # so it's important to keep lives > 0, so that we only reset once
            # the environment advertises done.
            done = True
        self.lives = lives
        return obs, reward, done, info

    def reset(self, **kwargs):
        """Reset only when lives are exhausted.
        This way all states are still reachable even though lives are episodic,
        and the learner need not know about any of this behind-the-scenes.
        """
        if self.was_real_done:
            obs = self.env.reset(**kwargs)
        else:
            # no-op step to advance from terminal/lost life state
            obs, _, _, _ = self.env.step(0)
        self.lives = self.env.unwrapped.ale.lives()
        return obs

class MaxAndSkipEnv(gym.Wrapper):
    def __init__(self, env, skip=4):
        """Return only every `skip`-th frame"""
        gym.Wrapper.__init__(self, env)
        # most recent raw observations (for max pooling across time steps)
        self._obs_buffer = np.zeros((2,)+env.observation_space.shape, dtype=np.uint8)
        self._skip       = skip

    def step(self, action):
        """Repeat action, sum reward, and max over last observations."""
        total_reward = 0.0
        done = None
        for i in range(self._skip):
            obs, reward, done, info = self.env.step(action)
            if i == self._skip - 2: self._obs_buffer[0] = obs
            if i == self._skip - 1: self._obs_buffer[1] = obs
            total_reward += reward
            if done:
                break
        # Note that the observation on the done=True frame
        # doesn't matter
        max_frame = self._obs_buffer.max(axis=0)

        return max_frame, total_reward, done, info

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)

class ClipRewardEnv(gym.RewardWrapper):
    def __init__(self, env):
        gym.RewardWrapper.__init__(self, env)

    def reward(self, reward):
        """Bin reward to {+1, 0, -1} by its sign."""
        return np.sign(reward)


class WarpFrame(gym.ObservationWrapper):
    def __init__(self, env, width=84, height=84, grayscale=True, dict_space_key=None):
        """
        Warp frames to 84x84 as done in the Nature paper and later work.
        If the environment uses dictionary observations, `dict_space_key` can be specified which indicates which
        observation should be warped.
        """
        super().__init__(env)
        self._width = width
        self._height = height
        self._grayscale = grayscale
        self._key = dict_space_key
        if self._grayscale:
            num_colors = 1
        else:
            num_colors = 3

        new_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(self._height, self._width, num_colors),
            dtype=np.uint8,
        )
        if self._key is None:
            original_space = self.observation_space
            self.observation_space = new_space
        else:
            original_space = self.observation_space.spaces[self._key]
            self.observation_space.spaces[self._key] = new_space
        assert original_space.dtype == np.uint8 and len(original_space.shape) == 3

    def observation(self, obs):
        if self._key is None:
            frame = obs
        else:
            frame = obs[self._key]

        if self._grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        frame = cv2.resize(
            frame, (self._width, self._height), interpolation=cv2.INTER_AREA
        )
        if self._grayscale:
            frame = np.expand_dims(frame, -1)

        if self._key is None:
            obs = frame
        else:
            obs = obs.copy()
            obs[self._key] = frame
        return obs


class FrameStack(gym.Wrapper):
    def __init__(self, env, k):
        """Stack k last frames.
        Returns lazy array, which is much more memory efficient.
        See Also
        --------
        baselines.common.atari_wrappers.LazyFrames
        """
        gym.Wrapper.__init__(self, env)
        self.k = k
        self.frames = deque([], maxlen=k)
        shp = env.observation_space.shape
        self.observation_space = spaces.Box(low=0, high=255, shape=((shp[0] * k,)+shp[1:]), dtype=env.observation_space.dtype)

    def reset(self):
        ob = self.env.reset()
        for _ in range(self.k):
            self.frames.append(ob)
        return self._get_ob()

    def step(self, action):
        ob, reward, done, info = self.env.step(action)
        self.frames.append(ob)
        return self._get_ob(), reward, done, info

    def _get_ob(self):
        assert len(self.frames) == self.k
        return np.concatenate(list(self.frames), axis=-1)

class ScaledFloatFrame(gym.ObservationWrapper):
    def __init__(self, env):
        gym.ObservationWrapper.__init__(self, env)
        self.observation_space = gym.spaces.Box(low=0, high=1, shape=env.observation_space.shape, dtype=np.float32)

    def observation(self, observation):
        # careful! This undoes the memory optimization, use
        # with smaller replay buffers only.
        return np.array(observation).astype(np.float32) / 255.0

class LazyFrames(object):
    def __init__(self, frames):
        """This object ensures that common frames between the observations are only stored once.
        It exists purely to optimize memory usage which can be huge for DQN's 1M frames replay
        buffers.
        This object should only be converted to numpy array before being passed to the model.
        You'd not believe how complex the previous solution was."""
        self._frames = frames
        self._out = None

    def _force(self):
        if self._out is None:
            self._out = np.concatenate(self._frames, axis=0)
            self._frames = None
        return self._out

    def __array__(self, dtype=None):
        out = self._force()
        if dtype is not None:
            out = out.astype(dtype)
        return out

    def __len__(self):
        return len(self._force())

    def __getitem__(self, i):
        return self._force()[i]

    def count(self):
        frames = self._force()
        return frames.shape[frames.ndim - 1]

    def frame(self, i):
        return self._force()[..., i]

def wrap_atari(env, max_episode_steps=None):
    assert 'NoFrameskip' in env.spec.id
    env = NoopResetEnv(env, noop_max=30)
    env = MaxAndSkipEnv(env, skip=4)

    assert max_episode_steps is None

    return env

class ImageToPyTorch(gym.ObservationWrapper):
    """
    Image shape to channels x weight x height
    """

    def __init__(self, env):
        super(ImageToPyTorch, self).__init__(env)
        old_shape = self.observation_space.shape
        self.observation_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(old_shape[-1], old_shape[0], old_shape[1]),
            dtype=np.uint8,
        )

    def observation(self, observation):
        return np.transpose(observation, axes=(2, 0, 1))

def wrap_deepmind(env, episode_life=True, clip_rewards=True, frame_stack=False, scale=False):
    """Configure environment for DeepMind-style Atari.
    """
    if episode_life:
        env = EpisodicLifeEnv(env)
    if 'FIRE' in env.unwrapped.get_action_meanings():
        env = FireResetEnv(env)
    env = WarpFrame(env)
    if scale:
        env = ScaledFloatFrame(env)
    if clip_rewards:
        env = ClipRewardEnv(env)
    # env = ImageToPyTorch(env)
    if frame_stack:
        env = FrameStack(env, 4)
    return env


# Reference: https://www.cs.toronto.edu/~vmnih/docs/dqn.pdf

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

import argparse
from distutils.util import strtobool
import collections
import numpy as np
import gym
from gym.wrappers import TimeLimit, Monitor
from gym.spaces import Discrete, Box, MultiBinary, MultiDiscrete, Space
import time
import random
import os

from cpprb import ReplayBuffer, PrioritizedReplayBuffer
import threading
os.environ["OMP_NUM_THREADS"] = "1"  # Necessary for multithreading.
from torch import multiprocessing as mp

class Scale(nn.Module):
    def __init__(self, scale):
        super().__init__()
        self.scale = scale

    def forward(self, x):
        return x * self.scale
class QNetwork(nn.Module):
    def __init__(self, device="cpu", frames=4):
        super(QNetwork, self).__init__()
        self.device = device
        self.device = device
        self.network = nn.Sequential(
            Scale(1/255),
            nn.Conv2d(frames, 32, 8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(3136, 512),
            nn.ReLU(),
            nn.Linear(512, env.action_space.n)
        )

    def forward(self, x):
        x = torch.Tensor(x).to(self.device)
        return self.network(x)

def linear_schedule(start_e: float, end_e: float, duration: int, t: int):
    slope =  (end_e - start_e) / duration
    if end_e < start_e:
        return max(slope * t + start_e, end_e)
    else:
        return min(slope * t + start_e, end_e)

def act(args, i, rb, q_network, target_network, lock, queues, queue, stats_queue, global_step, device, writer):
    env = gym.make(args.gym_id)
    env = wrap_atari(env)
    env = gym.wrappers.RecordEpisodeStatistics(env) # records episode reward in `info['episode']['r']`
    if args.capture_video:
        env = Monitor(env, f'videos/{experiment_name}')
    env = wrap_deepmind(
        env,
        clip_rewards=True,
        frame_stack=True,
        scale=False,
    )
    env.seed(args.seed+i)
    env.action_space.seed(args.seed+i)
    # TRY NOT TO MODIFY: start the game
    obs = env.reset()
    # local_rb = PrioritizedReplayBuffer(10000, args.pr_alpha)
    episode_reward = 0
    update_step = 0
    while global_step < (args.total_timesteps):
        update_step += 1
        # global_step *= args.num_actor
        # ALGO LOGIC: put action logic here
        epsilon = linear_schedule(args.start_e, args.end_e, args.exploration_fraction*args.total_timesteps, global_step)
        obs = np.array(obs)
        if random.random() < epsilon:
            action = env.action_space.sample()
        else:
            logits = q_network.forward(obs.reshape((1,)+obs.shape))
            action = torch.argmax(logits, dim=1).tolist()[0]
        # action = env.action_space.sample()
    
        # TRY NOT TO MODIFY: execute the game and log data.
        next_obs, reward, done, info = env.step(action)
        episode_reward += reward
        # local_rb.add(obs, action, reward, next_obs, float(done))
        
        # TRY NOT TO MODIFY: record rewards for plotting purposes
        # if global_step > args.learning_starts:
        #     if len(local_rb) >= args.actor_buffer_size:
        #         beta = linear_schedule(args.pr_beta0, 1.0, args.total_timesteps, global_step)
        #         experience = local_rb.sample(args.actor_buffer_size, beta=beta)
        #         (s_obs, s_actions, s_rewards, s_next_obses, s_dones, s_weights, s_batch_idxes) = experience
        #         with torch.no_grad():
        #             # target_max = torch.max(target_network.forward(s_next_obses), dim=1)[0]
        #             current_value = q_network.forward(s_next_obses)
        #             target_value = target_network.forward(s_next_obses)
        #             target_max = target_value.gather(1, torch.max(current_value, 1)[1].unsqueeze(1)).squeeze(1)
        #             td_target = torch.Tensor(s_rewards).to(device) + args.gamma * target_max * (1 - torch.Tensor(s_dones).to(device))
        #             old_val = q_network.forward(s_obs).gather(1, torch.LongTensor(s_actions).view(-1,1).to(device)).squeeze()
        #             td_errors = td_target - old_val
        #         new_priorities = np.abs(td_errors.tolist()) + args.pr_eps
        #         local_rb.update_priorities(s_batch_idxes, new_priorities)
        with lock:
            rb.add(obs, action, reward, next_obs, float(done))
            global_step += 1
            if 'episode' in info.keys():
                stats_queue.put((info['episode']['r'], info['episode']['l']))
            print(rb._it_sum.sum())
            print(rb)
            raise
            # if len(local_rb) >= args.actor_buffer_size:
            #     for i in range(len(s_obs)):
            #         rb.add_with_priority(new_priorities[i], s_obs[i], s_actions[i], s_rewards[i], s_next_obses[i], s_dones[i])
            # local_rb = PrioritizedReplayBuffer(10000, args.pr_alpha)
        # if global_step > args.learning_starts and update_step % args.train_frequency == 0:
        #     update_step += 1
        #     beta = linear_schedule(args.pr_beta0, 1.0, args.total_timesteps, global_step)
        #     experience = rb.sample(args.batch_size, beta=beta)
        #     (s_obs, s_actions, s_rewards, s_next_obses, s_dones, s_weights, s_batch_idxes) = experience
        #     # s_obs, s_actions, s_rewards, s_next_obses, s_dones = rb.sample(args.batch_size)
        #     with torch.no_grad():
        #         # target_max = torch.max(learn_target_network.forward(s_next_obses), dim=1)[0]
        #         current_value = q_network.forward(s_next_obses)
        #         target_value = learn_target_network.forward(s_next_obses)
        #         target_max = target_value.gather(1, torch.max(current_value, 1)[1].unsqueeze(1)).squeeze(1)
        #         td_target = torch.Tensor(s_rewards).to(device) + args.gamma * target_max * (1 - torch.Tensor(s_dones).to(device))
    
        #     old_val = q_network.forward(s_obs).gather(1, torch.LongTensor(s_actions).view(-1,1).to(device)).squeeze()
        #     td_errors = td_target - old_val
        #     # update the weights in the prioritized replay
        #     new_priorities = np.abs(td_errors.tolist()) + args.pr_eps
        #     rb.update_priorities(s_batch_idxes, new_priorities)
        
        # TRY NOT TO MODIFY: CRUCIAL step easy to overlook 
        obs = next_obs
        if done:
            # important to note that because `EpisodicLifeEnv` wrapper is applied,
            # the real episode reward is actually the sum of episode reward of 5 lives
            # which we record through `info['episode']['r']` provided by gym.wrappers.RecordEpisodeStatistics
            obs, episode_reward = env.reset(), 0

def learn(args, rb, global_step, queues, queue, lock, learn_target_network, target_network, learn_q_network, q_network, optimizer, device):
    loss_fn = nn.MSELoss()
    update_step = 0
    # time.sleep(10)
    while global_step < (args.total_timesteps):
        if global_step > args.learning_starts and update_step % args.train_frequency == 0:
            # with lock:
            update_step += 1
            beta = linear_schedule(args.pr_beta0, 1.0, args.total_timesteps, global_step)
            # s_obs, s_actions, s_rewards, s_next_obses, s_dones = queues[0].get(), queues[1].get(), queues[2].get(), queues[3].get(), queues[4].get()
            # s_obs, s_actions, s_rewards, s_next_obses, s_dones = [item.to(device) for item in queue.get()]
            # s_obs, s_actions, s_rewards, s_next_obses, s_dones = queues[0].get().to(device), queues[1].get().to(device), queues[2].get().to(device), queues[3].get().to(device), queues[4].get().to(device)
            experience = rb.sample(args.batch_size, beta=beta)
            (s_obs, s_actions, s_rewards, s_next_obses, s_dones, s_weights, s_batch_idxes) = experience
            # s_obs, s_actions, s_rewards, s_next_obses, s_dones = rb.sample(args.batch_size)
            with torch.no_grad():
                # target_max = torch.max(learn_target_network.forward(s_next_obses), dim=1)[0]
                current_value = q_network.forward(s_next_obses)
                target_value = learn_target_network.forward(s_next_obses)
                target_max = target_value.gather(1, torch.max(current_value, 1)[1].unsqueeze(1)).squeeze(1)
                td_target = torch.Tensor(s_rewards).to(device) + args.gamma * target_max * (1 - torch.Tensor(s_dones).to(device))
    
            old_val = q_network.forward(s_obs).gather(1, torch.LongTensor(s_actions).view(-1,1).to(device)).squeeze()
            td_errors = td_target - old_val
            
            loss = (td_errors ** 2).mean()
            writer.add_scalar("losses/td_loss", loss, global_step)
            
            # update the weights in the prioritized replay
            new_priorities = np.abs(td_errors.tolist()) + args.pr_eps
            rb.update_priorities(s_batch_idxes, new_priorities)
            
            # if global_step % 100 == 0:
            #     writer.add_scalar("losses/td_loss", loss, update_step+args.learning_starts)
        
            # optimize the midel
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(list(learn_q_network.parameters()), args.max_grad_norm)
            optimizer.step()
            
            # the actor models are a little delayed and needs to be updated
            # if update_step % 1 == 0:
            q_network.load_state_dict(learn_q_network.state_dict())
        
            # update the target network
            if update_step % args.target_network_frequency == 0:
                learn_target_network.load_state_dict(learn_q_network.state_dict())
                target_network.load_state_dict(learn_q_network.state_dict())
                print("updated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DQN agent')
    # Common arguments
    parser.add_argument('--exp-name', type=str, default=os.path.basename(__file__).rstrip(".py"),
                        help='the name of this experiment')
    parser.add_argument('--gym-id', type=str, default="BreakoutNoFrameskip-v4",
                        help='the id of the gym environment')
    parser.add_argument('--learning-rate', type=float, default=1e-4,
                        help='the learning rate of the optimizer')
    parser.add_argument('--seed', type=int, default=2,
                        help='seed of the experiment')
    parser.add_argument('--total-timesteps', type=int, default=10000000,
                        help='total timesteps of the experiments')
    parser.add_argument('--torch-deterministic', type=lambda x:bool(strtobool(x)), default=True, nargs='?', const=True,
                        help='if toggled, `torch.backends.cudnn.deterministic=False`')
    parser.add_argument('--cuda', type=lambda x:bool(strtobool(x)), default=True, nargs='?', const=True,
                        help='if toggled, cuda will not be enabled by default')
    parser.add_argument('--prod-mode', type=lambda x:bool(strtobool(x)), default=False, nargs='?', const=True,
                        help='run the script in production mode and use wandb to log outputs')
    parser.add_argument('--capture-video', type=lambda x:bool(strtobool(x)), default=False, nargs='?', const=True,
                        help='weather to capture videos of the agent performances (check out `videos` folder)')
    parser.add_argument('--wandb-project-name', type=str, default="cleanRL",
                        help="the wandb's project name")
    parser.add_argument('--wandb-entity', type=str, default=None,
                        help="the entity (team) of wandb's project")
    
    # Algorithm specific arguments
    parser.add_argument('--num-actor', type=int, default=4,
                         help='the replay memory buffer size')
    parser.add_argument('--actor-buffer-size', type=int, default=50,
                         help='the replay memory buffer size')
    parser.add_argument('--buffer-size', type=int, default=100000,
                         help='the replay memory buffer size')
    parser.add_argument('--pr-alpha', type=float, default=0.6,
                        help='alpha parameter for prioritized replay buffer')
    parser.add_argument('--pr-beta0', type=float, default=0.4,
                        help='initial value of beta for prioritized replay buffer')
    parser.add_argument('--pr-eps', type=float, default=1e-6,
                        help='epsilon to add to the TD errors when updating priorities.')
    parser.add_argument('--gamma', type=float, default=0.99,
                        help='the discount factor gamma')
    parser.add_argument('--target-network-frequency', type=int, default=1000,
                        help="the timesteps it takes to update the target network")
    parser.add_argument('--max-grad-norm', type=float, default=0.5,
                        help='the maximum norm for the gradient clipping')
    parser.add_argument('--batch-size', type=int, default=32,
                        help="the batch size of sample from the reply memory")
    parser.add_argument('--start-e', type=float, default=1.,
                        help="the starting epsilon for exploration")
    parser.add_argument('--end-e', type=float, default=0.02,
                        help="the ending epsilon for exploration")
    parser.add_argument('--exploration-fraction', type=float, default=0.10,
                        help="the fraction of `total-timesteps` it takes from start-e to go end-e")
    parser.add_argument('--learning-starts', type=int, default=80000,
                        help="timestep to start learning")
    parser.add_argument('--train-frequency', type=int, default=4,
                        help="the frequency of training")
    args = parser.parse_args()
    if not args.seed:
        args.seed = int(time.time())
    
    # TRY NOT TO MODIFY: setup the environment
    experiment_name = f"{args.gym_id}__{args.exp_name}__{args.seed}__{int(time.time())}"
    writer = SummaryWriter(f"runs/{experiment_name}")
    writer.add_text('hyperparameters', "|param|value|\n|-|-|\n%s" % (
            '\n'.join([f"|{key}|{value}|" for key, value in vars(args).items()])))
    if args.prod_mode:
        import wandb
        wandb.init(project=args.wandb_project_name, entity=args.wandb_entity, sync_tensorboard=True, config=vars(args), name=experiment_name, monitor_gym=True, save_code=True)
        writer = SummaryWriter(f"/tmp/{experiment_name}")
    
    # TRY NOT TO MODIFY: seeding
    device = torch.device('cuda' if torch.cuda.is_available() and args.cuda else 'cpu')
    env = gym.make(args.gym_id)
    env = wrap_atari(env)
    env = gym.wrappers.RecordEpisodeStatistics(env) # records episode reward in `info['episode']['r']`
    if args.capture_video:
        env = Monitor(env, f'videos/{experiment_name}')
    env = wrap_deepmind(
        env,
        clip_rewards=True,
        frame_stack=True,
        scale=False,
    )
    env.seed(args.seed)
    env.action_space.seed(args.seed)
    env.observation_space.seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic
    
    # respect the default timelimit
    assert isinstance(env.action_space, Discrete), "only discrete action space is supported"
    
    raise
    
    rb = PrioritizedReplayBuffer(args.buffer_size, args.pr_alpha)
    
    rb = PrioritizedReplayBuffer(1000,
                              {"obs": {},
                               "act": {}, # "shape": 1
                               "rew": {},
                               "next_obs": {},
                               "done": {}},
                              # next_of = "obs", stack_compress = "obs",
                              alpha=0.6)

    q_network = QNetwork()
    q_network.share_memory()
    target_network = QNetwork()
    target_network.share_memory()
    target_network.load_state_dict(q_network.state_dict())
    print(device.__repr__())
    print(q_network)
    learn_q_network = QNetwork(device).to(device)
    learn_q_network.share_memory()
    learn_q_network.load_state_dict(q_network.state_dict())
    learn_target_network = QNetwork(device).to(device)
    learn_target_network.share_memory()
    learn_target_network.load_state_dict(q_network.state_dict())
    optimizer = optim.Adam(learn_q_network.parameters(), lr=args.learning_rate)
    
    
    global_step = torch.tensor(0)
    global_step.share_memory_()
    actor_processes = []
    ctx = mp.get_context("forkserver")
    queue = ctx.Queue(1000)
    queues = None
    stats_queue = ctx.SimpleQueue()
    m = mp.Manager()
    lock = m.Lock()
    for i in range(4):
        actor = ctx.Process(
            target=act,
            args=(
                args,
                i,
                rb,
                q_network,
                target_network,
                lock,
                queues, queue,
                stats_queue,
                global_step,
                "cpu",
                None
            ),
        )
        actor.start()
        actor_processes.append(actor)
    
    # for actor in actor_processes:
    #     actor.join()


    learner_processes = []
    lm = mp.Manager()
    llock = lm.Lock()
    for i in range(1):
        learner = ctx.Process(
            target=learn,
            args=(
                args, rb, global_step,
                queues, queue, llock, learn_target_network, target_network, learn_q_network, q_network, optimizer, device
            ),
        )
        learner.start()
        learner_processes.append(learner)

    approx_global_step= 0
    start_time = time.time()
    import timeit
    while True:
        r, l = stats_queue.get()
        approx_global_step += l
        print(f"global_step={approx_global_step}, episode_reward={r}")
        writer.add_scalar("charts/episode_reward", r, approx_global_step)
        writer.add_scalar("charts/qsize", queue.qsize(), approx_global_step)
        print(queue.qsize())
        sps = int((approx_global_step) / (time.time() - start_time))
        print(sps)
        writer.add_scalar("charts/sps", sps, approx_global_step)
        print(rb._it_sum.sum())
        
        del r, l
        # print(list(q_network.network)[-1].weight.sum().item())
        # print(list(learn_q_network.network)[-1].weight.sum().item())
        # update_step += 1
        # s_obs, s_actions, s_rewards, s_next_obses, s_dones = queues[0].get(), queues[1].get(), queues[2].get(), queues[3].get(), queues[4].get()
        # s_obs, s_actions, s_rewards, s_next_obses, s_dones = queues[0].get().to(device), queues[1].get().to(device), queues[2].get().to(device), queues[3].get().to(device), queues[4].get().to(device)
        # with torch.no_grad():
        #     target_max = torch.max(target_network.forward(s_next_obses), dim=1)[0]
        #     td_target = s_rewards + args.gamma * target_max * (1 - s_dones)
        # old_val = learn_q_network.forward(s_obs).gather(1, s_actions.long().view(-1,1)).squeeze()
        # loss = loss_fn(td_target, old_val)
        
        # if global_step % 100 == 0:
        #     writer.add_scalar("losses/td_loss", loss, update_step+args.learning_starts)
    
        # # optimize the midel
        # optimizer.zero_grad()
        # loss.backward()
        # nn.utils.clip_grad_norm_(list(q_network.parameters()), args.max_grad_norm)
        # optimizer.step()
        
        # # the actor models are a little delayed and needs to be updated
        # if update_step % 20 == 0:
        #     q_network.load_state_dict(learn_q_network.state_dict())
    
        # # update the target network
        # if update_step % args.target_network_frequency == 0:
        #     target_network.load_state_dict(q_network.state_dict())
        #     print("updated")



# # env.close()
# # writer.close()