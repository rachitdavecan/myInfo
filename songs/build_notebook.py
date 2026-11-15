"""Builds the ACE-Step 1.5 Colab notebook for the Shiv Panchakshar devotional rap."""
import json
import sys

OUT = sys.argv[1]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text, form=False):
    meta = {"cellView": "form"} if form else {}
    return {"cell_type": "code", "metadata": meta, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


LYRICS_DEVANAGARI = """[Intro]
हर हर महादेव! बम बम भोले!
ॐ नमः शिवाय

[Chorus]
नागेन्द्रहाराय त्रिलोचनाय
भस्माङ्गरागाय महेश्वराय
नित्याय शुद्धाय दिगम्बराय
तस्मै नकाराय नमः शिवाय

[Verse 1]
कैलाश की चोटी पे बैठा, ध्यान में है मगन
गले में नाग, जटा में गंगा, माथे पे चंदन
तीन नेत्र खुले तो काँपे ये सारा गगन
भस्म लगाया तन पे, फिर भी सबसे उजला मन
ना महल, ना सोना, ना कोई ताज चाहिए
बस एक लोटा जल और सच्ची आवाज़ चाहिए
जो झुका उनके आगे, वो कभी ना हार पाए
हर साँस में एक नाम, ॐ नमः शिवाय

[Chorus]
मन्दाकिनी सलिल चन्दन चर्चिताय
नन्दीश्वर प्रमथनाथ महेश्वराय
मन्दार पुष्प बहुपुष्प सुपूजिताय
तस्मै मकाराय नमः शिवाय

[Verse 2]
दक्ष का घमंड टूटा, यज्ञ हुआ राख
वीरभद्र जब उतरा, झुकी सबकी आँख
समुद्र मंथन में जब निकला था ज़हर
नीलकंठ ने पी लिया, रुक गया हर कहर
नंदी खड़ा द्वार पे, गौरी संग में
डमरू की धुन पे नाचे सृष्टि हर रंग में
तांडव जब शुरू हो, तो थम जाए काल
महाकाल के आगे कौन करेगा सवाल

[Chorus]
शिवाय गौरी वदनाब्ज वृन्द सूर्याय
दक्षाध्वर नाशकाय
श्री नीलकण्ठाय वृषध्वजाय
तस्मै शिकाराय नमः शिवाय

[Bridge]
वसिष्ठ कुम्भोद्भव गौतमार्य
मुनीन्द्र देवार्चित शेखराय
चन्द्रार्क वैश्वानर लोचनाय
तस्मै वकाराय नमः शिवाय

[Verse 3]
ना शुरू, ना अंत, वो अनादि, वो अनंत
वसिष्ठ, गौतम झुके, झुके सारे संत
सूर्य, चंद्र, अग्नि, तीनों उनकी आँख
पिनाक उनके हाथ में, भक्तों पे उनका हाथ
पंच अक्षर का मंत्र, न, म, शि, वा, य
पाँच तत्व का सार, जिसने समझा उसने पाया
दुनिया की दौड़ में जब मन भटक जाए
बस एक बार बोल, ॐ नमः शिवाय

[Chorus]
यक्षस्वरूपाय जटाधराय
पिनाकहस्ताय सनातनाय
दिव्याय देवाय दिगम्बराय
तस्मै यकाराय नमः शिवाय

[Chorus]
नागेन्द्रहाराय त्रिलोचनाय
भस्माङ्गरागाय महेश्वराय
नित्याय शुद्धाय दिगम्बराय
तस्मै नकाराय नमः शिवाय

[Outro]
पञ्चाक्षरमिदं पुण्यं यः पठेच्छिवसन्निधौ
शिवलोकमवाप्नोति शिवेन सह मोदते
ॐ नमः शिवाय, हर हर महादेव"""

LYRICS_ROMAN = """[Intro]
Har Har Mahadev! Bam Bam Bhole!
Om Namah Shivaya

[Chorus]
Nagendraharaya Trilochanaya
Bhasmangaragaya Maheshvaraya
Nityaya Shuddhaya Digambaraya
Tasmai Na-karaya Namah Shivaya

[Verse 1]
Kailash ki choti pe baitha, dhyaan mein hai magan
Gale mein naag, jata mein Ganga, maathe pe chandan
Teen netra khule toh kaanpe ye saara gagan
Bhasm lagaya tan pe, phir bhi sabse ujla mann
Na mahal, na sona, na koi taaj chahiye
Bas ek lota jal aur sachchi aawaaz chahiye
Jo jhuka unke aage, wo kabhi na haar paaye
Har saans mein ek naam, Om Namah Shivaye

[Chorus]
Mandakini Salila Chandana Charchitaya
Nandishvara Pramathanatha Maheshvaraya
Mandara Pushpa Bahupushpa Supujitaya
Tasmai Ma-karaya Namah Shivaya

[Verse 2]
Daksh ka ghamand toota, yagya hua raakh
Veerbhadra jab utra, jhuki sabki aankh
Samudra manthan mein jab nikla tha zeher
Neelkanth ne pee liya, ruk gaya har kehar
Nandi khada dwaar pe, Gauri sang mein
Damru ki dhun pe naache srishti har rang mein
Tandav jab shuru ho, toh tham jaaye kaal
Mahakaal ke aage kaun karega sawaal

[Chorus]
Shivaya Gauri Vadanabja Vrinda Suryaya
Dakshadhvara Nashakaya
Shri Neelakanthaya Vrishadhvajaya
Tasmai Shi-karaya Namah Shivaya

[Bridge]
Vasishtha Kumbhodbhava Gautamarya
Munindra Devarchita Shekharaya
Chandrarka Vaishvanara Lochanaya
Tasmai Va-karaya Namah Shivaya

[Verse 3]
Na shuru, na ant, wo anaadi, wo anant
Vasishtha, Gautam jhuke, jhuke saare sant
Surya, Chandra, Agni, teeno unki aankh
Pinaak unke haath mein, bhakton pe unka haath
Panch akshar ka mantra, Na, Ma, Shi, Va, Ya
Paanch tatva ka saar, jisne samjha usne paaya
Duniya ki daud mein jab mann bhatak jaaye
Bas ek baar bol, Om Namah Shivaye

[Chorus]
Yaksha Svarupaya Jatadharaya
Pinaka Hastaya Sanatanaya
Divyaya Devaya Digambaraya
Tasmai Ya-karaya Namah Shivaya

[Chorus]
Nagendraharaya Trilochanaya
Bhasmangaragaya Maheshvaraya
Nityaya Shuddhaya Digambaraya
Tasmai Na-karaya Namah Shivaya

[Outro]
Panchaksharam Idam Punyam Yah Pathet Shiva Sannidhau
Shivalokam Avapnoti Shivena Saha Modate
Om Namah Shivaya, Har Har Mahadev"""

# Pure-Sanskrit version laid out like the reference track (Saundarya Lahari "Avidyanam" song):
# ~5 s intro -> two fast rhythmic-chant verses (~70 s) -> short breakdown -> big slower drop -> fade.
SANSKRIT_DEVANAGARI = """[Intro]
ॐ नमः शिवाय

[Verse 1]
नागेन्द्रहाराय त्रिलोचनाय
भस्माङ्गरागाय महेश्वराय
नित्याय शुद्धाय दिगम्बराय
तस्मै नकाराय नमः शिवाय
मन्दाकिनी सलिल चन्दन चर्चिताय
नन्दीश्वर प्रमथनाथ महेश्वराय
मन्दार पुष्प बहुपुष्प सुपूजिताय
तस्मै मकाराय नमः शिवाय

[Verse 2]
शिवाय गौरी वदनाब्ज वृन्द सूर्याय
दक्षाध्वर नाशकाय
श्री नीलकण्ठाय वृषध्वजाय
तस्मै शिकाराय नमः शिवाय
वसिष्ठ कुम्भोद्भव गौतमार्य
मुनीन्द्र देवार्चित शेखराय
चन्द्रार्क वैश्वानर लोचनाय
तस्मै वकाराय नमः शिवाय

[Bridge]
ॐ नमः शिवाय
हर हर महादेव

[Chorus]
यक्षस्वरूपाय जटाधराय
पिनाकहस्ताय सनातनाय
दिव्याय देवाय दिगम्बराय
तस्मै यकाराय नमः शिवाय
पञ्चाक्षरमिदं पुण्यं यः पठेच्छिवसन्निधौ
शिवलोकमवाप्नोति शिवेन सह मोदते

[Outro]
नागेन्द्रहाराय त्रिलोचनाय
तस्मै नकाराय नमः शिवाय"""

SANSKRIT_ROMAN = """[Intro]
Om Namah Shivaya

[Verse 1]
Nagendraharaya Trilochanaya
Bhasmangaragaya Maheshvaraya
Nityaya Shuddhaya Digambaraya
Tasmai Na-karaya Namah Shivaya
Mandakini Salila Chandana Charchitaya
Nandishvara Pramathanatha Maheshvaraya
Mandara Pushpa Bahupushpa Supujitaya
Tasmai Ma-karaya Namah Shivaya

[Verse 2]
Shivaya Gauri Vadanabja Vrinda Suryaya
Dakshadhvara Nashakaya
Shri Neelakanthaya Vrishadhvajaya
Tasmai Shi-karaya Namah Shivaya
Vasishtha Kumbhodbhava Gautamarya
Munindra Devarchita Shekharaya
Chandrarka Vaishvanara Lochanaya
Tasmai Va-karaya Namah Shivaya

[Bridge]
Om Namah Shivaya
Har Har Mahadev

[Chorus]
Yaksha Svarupaya Jatadharaya
Pinaka Hastaya Sanatanaya
Divyaya Devaya Digambaraya
Tasmai Ya-karaya Namah Shivaya
Panchaksharam Idam Punyam Yah Pathet Shiva Sannidhau
Shivalokam Avapnoti Shivena Saha Modate

[Outro]
Nagendraharaya Trilochanaya
Tasmai Na-karaya Namah Shivaya"""

ENGLISH_RAP_1 = """[Rap - English]
Ash on his skin and the moon in his hair
Serpent round his neck, there's a fire in the air
Three eyes open and the whole world shakes
Silence on Kailash, every mountain awakes
He don't need gold, he don't need a throne
Sitting in the snow, but he's never alone
Ganga in his locks and the damru in his hand
One name echoes, Shiva, understand"""

ENGLISH_RAP_2 = """[Rap - English]
When the ocean got churned and the poison came out
Every god ran scared, every heart filled with doubt
He drank it all down, held it still in his throat
Neelkanth, blue fire, that's the hope that I quote
Daksha had the pride but the pride turned to dust
Tandav on the beat, in Mahadev we trust
Five sacred letters, Na Ma Shi Va Ya
Every breath I take, Om Namah Shivaya"""


def with_english(lyrics):
    lyrics = lyrics.replace("\n\n[Verse 2]", "\n\n" + ENGLISH_RAP_1 + "\n\n[Verse 2]", 1)
    return lyrics.replace("\n\n[Bridge]", "\n\n" + ENGLISH_RAP_2 + "\n\n[Bridge]", 1)


ENGLISH_MIX_DEVANAGARI = with_english(SANSKRIT_DEVANAGARI)
ENGLISH_MIX_ROMAN = with_english(SANSKRIT_ROMAN)

CAPTION_ENGLISH = ("Dark cinematic devotional hip-hop for Lord Shiva. Deep male voice chanting a Sanskrit stotra "
                   "as fast rhythmic rap-chant, switching to hard-hitting English rap verses with confident "
                   "flow. Heavy sub bass, booming 808 trap drums, dark E minor, tanpura drone, damru, temple "
                   "bells, conch, ambient pads. Short breakdown, then a huge drop with sustained chanting and "
                   "choir. Intense, hypnotic, spiritual.")

CAPTION_MATCHED = ("Dark cinematic Sanskrit devotional hip-hop for Lord Shiva. Deep male voice delivering a "
                   "Sanskrit stotra as fast rhythmic rap-chant, tight flow on the beat. Heavy sub bass, "
                   "booming 808 trap drums, dark E minor, tanpura drone, damru, temple bells, conch, "
                   "ambient pads. Verses dense and driving, short breakdown, then a huge powerful drop "
                   "with sustained chanting and choir. Intense, hypnotic, spiritual.")

CAPTION = ("Epic Indian devotional hip-hop song for Lord Shiva. Deep powerful male voice chanting a "
           "Sanskrit stotra hook with temple choir, aggressive fast Hindi male rap verses. Heavy 808 "
           "trap drums, damru rolls, dhol, conch shell, temple bells, shehnai, tanpura drone, "
           "cinematic, intense, spiritual, goosebumps.")

GENERATE_PY = r'''
%%writefile /content/generate.py
"""Generate the song with ACE-Step 1.5 using the settings saved in /content/song.json."""
import json
import os
import sys

ROOT = "/content/ACE-Step-1.5"
os.environ.setdefault("ACESTEP_CHECKPOINTS_DIR", os.path.join(ROOT, "checkpoints"))

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

song = json.load(open("/content/song.json", encoding="utf-8"))

# 1) Music model (DiT). CPU offload keeps it inside the free T4's 15 GB.
dit = AceStepHandler()
msg, ok = dit.initialize_service(
    project_root=ROOT,
    config_path="acestep-v15-turbo",
    device="cuda",
    offload_to_cpu=True,
)
print(msg)
if not ok:
    sys.exit("Music model failed to load - see the message above.")

# 2) Planner language model (helps with structure / timing). Optional.
llm = LLMHandler()
use_lm = song["use_planner"]
if use_lm:
    msg, lm_ok = llm.initialize(
        checkpoint_dir=os.environ["ACESTEP_CHECKPOINTS_DIR"],
        lm_model_path="acestep-5Hz-lm-1.7B",
        backend="pt",
        device="cuda",
        offload_to_cpu=True,
    )
    print(msg)
    if not lm_ok:
        print("Planner failed to load - continuing without it.")
        use_lm = False

seed = song["seed"]
params = GenerationParams(
    caption=song["caption"],
    lyrics=song["lyrics"],
    vocal_language=song["language"],
    bpm=song["bpm"],
    keyscale=song["key"],
    timesignature="4",
    shift=3.0,               # recommended for the turbo model
    duration=song["duration"],
    thinking=use_lm,
    use_cot_caption=False,   # keep our style description exactly as written
    use_cot_language=False,  # keep the language we chose
    seed=seed,
)
config = GenerationConfig(
    batch_size=song["versions"],
    use_random_seed=seed < 0,
    seeds=None if seed < 0 else [seed + i for i in range(song["versions"])],
    audio_format="mp3",
)

result = generate_music(dit, llm, params, config, save_dir="/content/outputs")
if not result.success:
    print("Generation failed:", result.error)
    print(result.status_message)
    sys.exit(1)

for a in result.audios:
    print("Saved:", a["path"], "| seed:", a["params"]["seed"])
'''

cells = [
    md("""
# 🔱 Om Namah Shivaya — Shiv Panchakshar Stotra (Devotional Rap)
### Made with **ACE-Step 1.5** (free, open-source AI music model)

This notebook turns the Shiv Panchakshar Stotra (*Nagendraharaya Trilochanaya…*) plus new Hindi rap verses into a full song with vocals.

**Before you start:** go to **Runtime → Change runtime type → T4 GPU → Save**.

Then run the cells **one by one, top to bottom** (click ▶ on each, wait for it to finish).

| Step | Time (approx.) |
|---|---|
| 1. Check GPU | seconds |
| 2. Install ACE-Step | 5–10 min |
| 3. Download models (~10 GB) | 5–10 min |
| 4. Choose lyrics & settings | seconds |
| 5. Generate the song | 2–6 min |
| 6. Listen & download | seconds |

Steps 2–3 are only needed once per Colab session. To make new versions, just re-run steps 4 → 6.
"""),
    md("## 1. Check the GPU\nYou should see a **Tesla T4** (or better). If you see an error, set the runtime to GPU (see above)."),
    code("!nvidia-smi"),
    md("## 2. Install ACE-Step 1.5\nThis uses the official install method (`uv sync`). Lots of text will scroll by — that's normal."),
    code("""
%cd /content
!test -d ACE-Step-1.5 || git clone --depth 1 https://github.com/ace-step/ACE-Step-1.5.git
%cd /content/ACE-Step-1.5
!pip install -q uv
!uv sync
"""),
    md("## 3. Download the models\nDownloads the main model (music model, voice/audio decoder, text encoder, planner) into `checkpoints/`."),
    code("""
%cd /content/ACE-Step-1.5
!ACESTEP_CHECKPOINTS_DIR=/content/ACE-Step-1.5/checkpoints uv run acestep-download
"""),
    md("""
## 4. Choose lyrics & settings
- **version** —
  - `Sanskrit + English rap` *(default)*: same as Matched, plus two English rap verses between the shlokas (~3 min).
  - `Matched to reference`: pure Sanskrit stotra delivered as a fast rap-chant, same feel as the *Avidyanam* song — ~103 BPM, E minor, heavy bass, ~2:20, intro → 2 fast verses → breakdown → big drop.
  - `With Hindi rap verses`: the longer ~4 min version with Hindi rap verses between the shlokas.
- **lyrics_script** — `Devanagari` usually gives better pronunciation. Try `Roman` if words come out wrong.
- **duration / bpm / key** — pre-set from the reference song; change if you like.
- **versions** — how many different takes to make at once (1–2 on a free T4).
- **seed** — `-1` = random every time. Put a number (e.g. `42`) to repeat a take you liked.
- **use_planner** — lets ACE-Step's planner work out structure/timing. Turn off if you run out of memory.
"""),
    code(f'''
#@title Song settings {{ display-mode: "form" }}
version = "Sanskrit + English rap"  #@param ["Sanskrit + English rap", "Matched to reference", "With Hindi rap verses"]
lyrics_script = "Devanagari"  #@param ["Devanagari", "Roman"]
duration = 0  #@param {{type:"slider", min:0, max:360, step:5}}
bpm = 103  #@param {{type:"integer"}}
key = "E minor"  #@param ["E minor", "auto", "D minor", "F# minor", "C minor"]
versions = 2  #@param {{type:"slider", min:1, max:4, step:1}}
seed = -1  #@param {{type:"integer"}}
use_planner = True  #@param {{type:"boolean"}}
#@markdown *duration 0 = automatic (≈190 s English mix, ≈150 s Matched, ≈240 s Hindi-rap)*

caption_matched = {CAPTION_MATCHED!r}
caption_hindi = {CAPTION!r}
caption_english = {CAPTION_ENGLISH!r}

english_mix_devanagari = """{ENGLISH_MIX_DEVANAGARI}"""

english_mix_roman = """{ENGLISH_MIX_ROMAN}"""

sanskrit_devanagari = """{SANSKRIT_DEVANAGARI}"""

sanskrit_roman = """{SANSKRIT_ROMAN}"""

hindi_devanagari = """{LYRICS_DEVANAGARI}"""

hindi_roman = """{LYRICS_ROMAN}"""

import json
script = "dev" if lyrics_script == "Devanagari" else "rom"
presets = {{
    "Sanskrit + English rap": (caption_english, english_mix_devanagari, english_mix_roman, "unknown", 190.0),
    "Matched to reference": (caption_matched, sanskrit_devanagari, sanskrit_roman, "sa", 150.0),
    "With Hindi rap verses": (caption_hindi, hindi_devanagari, hindi_roman, "hi", 240.0),
}}
cap, lyr_dev, lyr_rom, lang, auto_dur = presets[version]
song = {{
    "caption": cap,
    "lyrics": lyr_dev if script == "dev" else lyr_rom,
    "language": lang,   # "unknown" = auto-detect, needed for mixed Sanskrit + English
    "duration": float(duration) if duration > 0 else auto_dur,
    "bpm": int(bpm),
    "key": "" if key == "auto" else key,
    "versions": int(versions),
    "seed": int(seed),
    "use_planner": bool(use_planner),
}}
json.dump(song, open("/content/song.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Saved: {{version}} | {{lyrics_script}} | {{song['duration']:.0f}} s | {{bpm}} BPM | {{key}} | {{versions}} take(s) | seed={{seed}}")
''', form=True),
    md("## 5. Generate the song 🎵\nThe first run takes longer because the models load into memory."),
    code(GENERATE_PY),
    code("""
%cd /content/ACE-Step-1.5
!ACESTEP_CHECKPOINTS_DIR=/content/ACE-Step-1.5/checkpoints uv run python /content/generate.py
"""),
    md("## 6. Listen & download"),
    code("""
import glob, os
from IPython.display import Audio, display

files = sorted(glob.glob("/content/outputs/**/*.mp3", recursive=True), key=os.path.getmtime)
if not files:
    print("No songs found yet - run step 5 first.")
for f in files:
    print(os.path.basename(f))
    display(Audio(f))
"""),
    code("""
# Download all generated songs to your computer
from google.colab import files as colab_files
import glob
for f in glob.glob("/content/outputs/**/*.mp3", recursive=True):
    colab_files.download(f)
"""),
    md("""
## Tips if it doesn't sound right
- **Generate again** (re-run steps 4 → 6). Every take is different — make 4–6 and keep the best.
- **Pronunciation off?** Switch `lyrics_script` between Devanagari and Roman, or spell a word the way it sounds.
- **Rap not aggressive enough?** Add words like `fast flow, hard-hitting, drill` to the style text in step 4.
- **Out of memory error?** Set `versions = 1` and/or untick `use_planner`.
- **Liked a take?** Note its seed (printed in step 5), set it in step 4, and tweak from there.

---
## Optional: use the full ACE-Step web app instead
Gives you a point-and-click interface (with editing, remixing, covers). Run the cell below, wait for a **`gradio.live`** link, and open it. Stop the cell to shut it down.
"""),
    code("""
%cd /content/ACE-Step-1.5
!ACESTEP_CHECKPOINTS_DIR=/content/ACE-Step-1.5/checkpoints uv run acestep --share --init_service true --config_path acestep-v15-turbo
"""),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4", "name": "Shiv_Panchakshar_Rap_ACE_Step.ipynb"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": cells,
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(nb, fh, ensure_ascii=False, indent=1)
print("wrote", OUT, len(cells), "cells")
