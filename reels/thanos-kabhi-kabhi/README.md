# Thanos x "Kabhi Kabhi Mere Dil Mein"

**Concept:** the ending of *Avengers: Infinity War*. After the snap, Thanos sits alone on his farm porch, watches the sunrise and gives a tiny smile. Playing Mukesh's "Kabhi Kabhie Mere Dil Mein" over it turns the universe's worst villain into a lonely poet.

## Shot plan (about 15s)
| Reel time | Visual | Audio |
|---|---|---|
| 0-4s | Thanos walking up / sitting down on the porch | soft song intro, or a little movie ambience |
| **~4s (HIT)** | he settles and looks at the sunrise | **"Kabhi kabhi mere dil mein..."** begins |
| 7s+ | close-up, the small smile | "...khayal aata hai" |
| last 1.2s | fade out | fade out |

## Steps
1. Get the scene clip (the last minute or so of Infinity War) as `scene.mp4`, plus the song as `song.mp3`.
2. Find two timestamps, using VLC or any player:
   - `SCENE_HIT`: the second Thanos sits or looks at the sun, in scene.mp4
   - `SONG_DROP`: the second the singer starts "Kabhi kabhi...", in song.mp3
3. Run:
   ```bash
   CLIP_START=10 SCENE_HIT=14.5 SONG_DROP=31.2 ./make_reel.sh scene.mp4 song.mp3 thanos_reel.mp4
   ```
4. Watch it. If the hook lands late, lower `SONG_DROP` by 0.1-0.3. If it lands early, raise it.

Optional knobs: `ORIG_VOL=0.15` keeps some movie ambience, `CLIP_LEN=20` makes it longer, and `TOP1/TOP2/LYRIC1/LYRIC2` change the text.

## Posting
- To avoid Instagram muting the reel: render with `ORIG_VOL=0`, then add the song from Instagram's music library and line up the hook by hand.
- Add emojis (🥲💜) in the Instagram or CapCut text tool.
- Caption idea: *"Villain bhi insaan hota hai 💜 #thanos #bollywoodedit"*
