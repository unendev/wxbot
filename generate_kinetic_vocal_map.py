import json
import os

import librosa
import numpy as np

# Paths
scratch_dir = r"C:\Users\a1634\.gemini\antigravity\brain\f0a529c9-c7ae-418e-974c-3011abeadad6\scratch"
song_dir = os.path.join(scratch_dir, "little_wish")
ogg_path = os.path.join(song_dir, "song.ogg")

print("=" * 50)
print("  BEAT SABER ARTIFICIAL INTELLIGENCE MAPPER (KINETIC-EAR)  ")
print("=" * 50)

# 1. AUDIO COGNITION ENGINE (听觉认知引擎)
print("Listening to 'song.ogg'...")
y, sr = librosa.load(ogg_path, sr=22050)
duration = librosa.get_duration(y=y, sr=sr)
print(f"Loaded song. Duration: {duration:.2f} seconds.")

bpm = 134.0
beat_duration = 60.0 / bpm  # ~0.44776 seconds per beat
total_beats = int(duration * bpm / 60.0)
print(f"BPM: {bpm}, Beat Duration: {beat_duration:.5f}s, Target Beats: {total_beats}")

# Full track energy envelope
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
times = librosa.times_like(onset_env, sr=sr)

# Separating low-frequency (drum kick/bass) and mid-high frequency (vocals/lead synth)
D = np.abs(librosa.stft(y))

# Normalize spectral profiles
bass_energy = np.sum(D[2:15, :], axis=0)
vocal_energy = np.sum(D[46:280, :], axis=0)

bass_energy = (bass_energy - np.min(bass_energy)) / (
    np.max(bass_energy) - np.min(bass_energy) + 1e-6
)
vocal_energy = (vocal_energy - np.min(vocal_energy)) / (
    np.max(vocal_energy) - np.min(vocal_energy) + 1e-6
)


def get_energy_at_time(time, energy_curve):
    idx = np.searchsorted(times, time)
    if idx >= len(energy_curve):
        return 0.0
    return float(energy_curve[idx])


print(
    "Audio processing complete. Low and High frequency transients extracted successfully."
)

# 2. MOTOR CONTROL STATE MACHINE (玩家运动物理状态机)
OPPOSITE_DIR = {0: 1, 1: 0, 2: 3, 3: 2, 4: 7, 7: 4, 5: 6, 6: 5, 8: 8}


class Hand:
    def __init__(self, color_type):
        self.color_type = color_type  # 0 = Red (Left), 1 = Blue (Right)
        self.last_x = 1 if color_type == 0 else 2
        self.last_y = 0
        self.last_direction = 1  # Standard start with a down-swing
        self.last_time = -99.0

    def move_to_and_swing(self, time, x, y, direction):
        self.last_x = x
        self.last_y = y
        self.last_direction = direction
        self.last_time = time
        return {
            "_time": round(time, 4),
            "_lineIndex": int(x),
            "_lineLayer": int(y),
            "_type": self.color_type,
            "_cutDirection": int(direction),
        }


def generate_cognitive_difficulty(diff_name):
    left_hand = Hand(0)
    right_hand = Hand(1)

    notes = []
    obstacles = []

    # We step beat-by-beat, subdivisions handled programmatically based on intensity and tempo
    b = 8.0  # Skip silent intro

    # Tuning parameters for highly dense and custom-looking maps
    # We lower vocal thresholds to capture more acoustic details (nuances) and boost overall note count
    vocal_threshold = 0.20 if diff_name == "ExpertPlus" else 0.32
    bass_threshold = 0.25 if diff_name == "ExpertPlus" else 0.35

    while b < total_beats - 4:
        time = b * beat_duration

        # Audio energy profiles at this instant
        v_energy = get_energy_at_time(time, vocal_energy)
        b_energy = get_energy_at_time(time, bass_energy)

        # Song sections
        is_intro = b < 40
        is_verse = (40 <= b < 104) or (200 <= b < 232)
        is_pre_chorus = (104 <= b < 136) or (264 <= b < 296)
        is_chorus = (136 <= b < 200) or (296 <= b < 360) or (424 <= b < 512)
        is_bridge = 360 <= b < 424
        is_outro = b >= 512

        if is_intro:
            # Intro: 1.0 beat step
            if b % 2.0 == 0:
                if b % 4.0 == 0:
                    notes.append(left_hand.move_to_and_swing(b, 1, 0, 1))
                else:
                    notes.append(right_hand.move_to_and_swing(b, 2, 0, 1))
            b += 1.0

        elif is_verse:
            # Verse: Step by 0.5 beat for fluid pacing
            step = 0.5

            # Subdivide beats if energy spikes to add subtle 1/4 vocal trills
            if diff_name == "ExpertPlus" and v_energy > 0.65 and b % 1.0 == 0:
                # Vocal roll三连音/快速双击
                ndir_l = OPPOSITE_DIR.get(left_hand.last_direction, 1)
                ndir_r = OPPOSITE_DIR.get(right_hand.last_direction, 1)
                notes.append(
                    left_hand.move_to_and_swing(b, 1, 0 if ndir_l == 1 else 1, ndir_l)
                )
                notes.append(
                    right_hand.move_to_and_swing(
                        b + 0.25, 2, 0 if ndir_r == 1 else 1, ndir_r
                    )
                )
            else:
                if v_energy > vocal_threshold:
                    if len(notes) % 2 == 0:
                        next_dir = OPPOSITE_DIR.get(left_hand.last_direction, 1)
                        next_y = 0 if next_dir == 1 else 1
                        notes.append(
                            left_hand.move_to_and_swing(b, 1, next_y, next_dir)
                        )
                    else:
                        next_dir = OPPOSITE_DIR.get(right_hand.last_direction, 1)
                        next_y = 0 if next_dir == 1 else 1
                        notes.append(
                            right_hand.move_to_and_swing(b, 2, next_y, next_dir)
                        )
            b += step

        elif is_pre_chorus:
            # Pre-Chorus tension
            step = 0.5
            if b % 0.5 == 0:
                # Add intense diagonal jumps as we get close to the chorus
                if (b // 0.5) % 2 == 0:
                    next_dir = 6 if left_hand.last_direction != 6 else 5
                    notes.append(
                        left_hand.move_to_and_swing(
                            b, 0, 0 if next_dir == 6 else 1, next_dir
                        )
                    )
                else:
                    next_dir = 7 if right_hand.last_direction != 7 else 4
                    notes.append(
                        right_hand.move_to_and_swing(
                            b, 3, 0 if next_dir == 7 else 1, next_dir
                        )
                    )
            b += step

        elif is_chorus:
            # Chorus: Maximum energy
            # 1. Heavy drum burst stream mapping
            is_stream_roll = (
                (b_energy > 0.55) and (diff_name == "ExpertPlus") and (b % 2.0 == 0)
            )

            if is_stream_roll:
                # Stream roll! 8 rapid alternate notes on 16ths
                for i in range(8):
                    curr_b = b + i * 0.25
                    if i % 2 == 0:
                        ndir = OPPOSITE_DIR.get(left_hand.last_direction, 1)
                        # Snake-like stream pattern: swing left hand column 1 -> 0 -> 1 -> 0
                        nx = 1 if (i // 2) % 2 == 0 else 0
                        notes.append(
                            left_hand.move_to_and_swing(
                                curr_b, nx, 0 if ndir == 1 else 1, ndir
                            )
                        )
                    else:
                        ndir = OPPOSITE_DIR.get(right_hand.last_direction, 1)
                        # Blue snake stream: column 2 -> 3 -> 2 -> 3
                        nx = 2 if (i // 2) % 2 == 0 else 3
                        notes.append(
                            right_hand.move_to_and_swing(
                                curr_b, nx, 0 if ndir == 1 else 1, ndir
                            )
                        )
                b += 2.0
            else:
                # 2. Crossover & Wide Jumps
                step = 0.5
                is_cross = (b % 4.0) >= 2.0

                if v_energy > vocal_threshold or b_energy > bass_threshold:
                    if is_cross:
                        # Crossover (Left goes to 2, Right goes to 1)
                        l_dir = OPPOSITE_DIR.get(left_hand.last_direction, 1)
                        r_dir = OPPOSITE_DIR.get(right_hand.last_direction, 1)
                        notes.append(
                            left_hand.move_to_and_swing(
                                b, 2, 0 if l_dir == 1 else 1, l_dir
                            )
                        )
                        notes.append(
                            right_hand.move_to_and_swing(
                                b + 0.25, 1, 0 if r_dir == 1 else 1, r_dir
                            )
                        )
                    else:
                        # Broad Wide Swing
                        l_dir = OPPOSITE_DIR.get(left_hand.last_direction, 1)
                        r_dir = OPPOSITE_DIR.get(right_hand.last_direction, 1)
                        notes.append(
                            left_hand.move_to_and_swing(
                                b, 0, 0 if l_dir == 1 else 1, l_dir
                            )
                        )
                        notes.append(
                            right_hand.move_to_and_swing(
                                b + 0.25, 3, 0 if r_dir == 1 else 1, r_dir
                            )
                        )
                b += step

        elif is_bridge:
            # Quiet emotional section. Flowing dot notes.
            step = 0.5
            if v_energy > 0.2:
                if b % 1.0 == 0:
                    notes.append(left_hand.move_to_and_swing(b, 1, 1, 8))
                elif b % 1.0 == 0.5:
                    notes.append(right_hand.move_to_and_swing(b, 2, 1, 8))
            b += step

        else:
            # Outro: heavy decaying impacts
            step = 1.0
            notes.append(left_hand.move_to_and_swing(b, 1, 0, 1))
            notes.append(right_hand.move_to_and_swing(b, 2, 0, 1))
            b += step

    # 3. SOUND STAGE FINAL VALIDATION (防重叠和极速冗余滤波)
    notes.sort(key=lambda x: x["_time"])

    # Strict collision checking
    filtered_notes = []
    last_r_time = -99.0
    last_b_time = -99.0

    for note in notes:
        t = note["_time"]
        ctype = note["_type"]

        if ctype == 0:  # Red (Left)
            # Physical flow filter
            if t - last_r_time >= 0.10:
                filtered_notes.append(note)
                last_r_time = t
        else:  # Blue (Right)
            if t - last_b_time >= 0.10:
                filtered_notes.append(note)
                last_b_time = t

    # Add dynamic obstacles (Wall hazards for chest swaying)
    current_wall = 16.0
    while current_wall < total_beats - 16:
        obstacles.append(
            {
                "_time": current_wall,
                "_lineIndex": 0,
                "_type": 0,
                "_duration": 2.0,
                "_width": 1,
            }
        )
        obstacles.append(
            {
                "_time": current_wall + 8.0,
                "_lineIndex": 3,
                "_type": 0,
                "_duration": 2.0,
                "_width": 1,
            }
        )
        current_wall += 16.0

    print(f"\n[{diff_name}] Engine simulated.")
    print(f"-> Generated {len(filtered_notes)} vocal/kinetic synced notes.")
    nps = len(filtered_notes) / duration
    print(f"-> Average NPS: {nps:.2f} notes/sec")
    print(f"-> Generated {len(obstacles)} active structural obstacles.")

    diff_data = {
        "_version": "2.0.0",
        "_notes": filtered_notes,
        "_obstacles": obstacles,
        "_events": [],
    }
    return diff_data


# Process map difficulty files
expert_data = generate_cognitive_difficulty("Expert")
expert_plus_data = generate_cognitive_difficulty("ExpertPlus")

# Write out standardized maps
with open(os.path.join(song_dir, "ExpertStandard.dat"), "w", encoding="utf-8") as f:
    json.dump(expert_data, f, indent=2, ensure_ascii=False)

with open(os.path.join(song_dir, "ExpertPlusStandard.dat"), "w", encoding="utf-8") as f:
    json.dump(expert_plus_data, f, indent=2, ensure_ascii=False)

# Re-link info.dat beatmaps
info_path = os.path.join(song_dir, "info.dat")
with open(info_path, "r", encoding="utf-8") as f:
    info = json.load(f)

diff_maps = [
    {
        "_difficulty": "Expert",
        "_difficultyRank": 7,
        "_beatmapFilename": "ExpertStandard.dat",
        "_noteJumpMovementSpeed": 15,
        "_noteJumpStartBeatOffset": 0,
        "_customData": {},
    },
    {
        "_difficulty": "ExpertPlus",
        "_difficultyRank": 9,
        "_beatmapFilename": "ExpertPlusStandard.dat",
        "_noteJumpMovementSpeed": 16,
        "_noteJumpStartBeatOffset": 0,
        "_customData": {},
    },
]

info["_difficultyBeatmapSets"][0]["_difficultyBeatmaps"] = diff_maps

with open(info_path, "w", encoding="utf-8") as f:
    json.dump(info, f, indent=2, ensure_ascii=False)

print(
    "\nSUCCESS: Soundscape Analyzed. Dual-Axis Cognitive maps compiled for Quest 3 standalone!"
)
print("=" * 50)
