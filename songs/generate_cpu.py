"""CPU-only ACE-Step 1.5 run for the Shiv Panchakshar (Sanskrit + English rap) song."""
import json
import os
import sys
import time

ROOT = sys.argv[1]          # ACE-Step checkout
SONG = sys.argv[2]          # song.json from the notebook settings cell
OUT = sys.argv[3]           # output folder
os.environ.setdefault("ACESTEP_CHECKPOINTS_DIR", os.path.join(ROOT, "checkpoints"))

import torch
torch.set_num_threads(os.cpu_count())

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

import gc

# CPU has only ~15 GB RAM: free the 8 GB diffusion model and text encoder before the VAE decode,
# and decode in smaller tiles. This is a one-shot run, so they are not needed afterwards.
_orig_decode = AceStepHandler._decode_generate_music_pred_latents


def _decode_low_mem(self, *args, **kwargs):
    self.model = None
    self.text_encoder = None
    gc.collect()
    print("freed DiT + text encoder before VAE decode", flush=True)
    return _orig_decode(self, *args, **kwargs)


AceStepHandler._decode_generate_music_pred_latents = _decode_low_mem

_orig_tiled = AceStepHandler.tiled_decode


def _tiled_small(self, latents, chunk_size=None, overlap=64, offload_wav_to_cpu=None):
    return _orig_tiled(self, latents, chunk_size=128, overlap=overlap, offload_wav_to_cpu=True)


AceStepHandler.tiled_decode = _tiled_small

song = json.load(open(SONG, encoding="utf-8"))
t0 = time.time()
dit = AceStepHandler()
msg, ok = dit.initialize_service(project_root=ROOT, config_path="acestep-v15-turbo", device="cpu")
print(msg, flush=True)
if not ok:
    sys.exit("DiT failed to load")
print(f"loaded in {time.time() - t0:.0f}s", flush=True)

llm = LLMHandler()  # not initialised: planner skipped on CPU to save time
params = GenerationParams(
    caption=song["caption"],
    lyrics=song["lyrics"],
    vocal_language=song["language"],
    bpm=song["bpm"],
    keyscale=song["key"],
    timesignature="4",
    duration=song["duration"],
    shift=3.0,
    thinking=False,
    use_cot_caption=False,
    use_cot_language=False,
    use_cot_metas=False,
    seed=int(sys.argv[4]) if len(sys.argv) > 4 else 42,
)
config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[params.seed], audio_format="mp3")
t1 = time.time()
result = generate_music(dit, llm, params, config, save_dir=OUT)
print(f"generation took {time.time() - t1:.0f}s", flush=True)
if not result.success:
    print("FAILED:", result.error, result.status_message)
    sys.exit(1)
for a in result.audios:
    print("Saved:", a["path"])
