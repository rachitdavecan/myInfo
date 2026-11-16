"""Lyric lines, meanings and per-take section timings for the Om Namah Shivaya lyric video."""

# Each section: (name, palette, [(text, script, meaning)])
# script: "dev" = Devanagari (Sanskrit/Hindi), "en" = English rap
SECTIONS = [
    ("intro", "intro", [
        ("ॐ नमः शिवाय", "dev", "Salutations to Shiva"),
    ]),
    ("verse1", "verse", [
        ("नागेन्द्रहाराय त्रिलोचनाय", "dev", "He who wears the king of serpents, the three-eyed one"),
        ("भस्माङ्गरागाय महेश्वराय", "dev", "Smeared with sacred ash, the Great Lord"),
        ("नित्याय शुद्धाय दिगम्बराय", "dev", "Eternal, pure, clothed by the sky"),
        ("तस्मै नकाराय नमः शिवाय", "dev", "To that 'Na' — salutations to Shiva"),
        ("मन्दाकिनी सलिल चन्दन चर्चिताय", "dev", "Anointed with Ganga's water and sandal paste"),
        ("नन्दीश्वर प्रमथनाथ महेश्वराय", "dev", "Lord of Nandi and of the Pramathas"),
        ("मन्दार पुष्प बहुपुष्प सुपूजिताय", "dev", "Worshipped with Mandara and countless flowers"),
        ("तस्मै मकाराय नमः शिवाय", "dev", "To that 'Ma' — salutations to Shiva"),
    ]),
    ("rap1", "rap", [
        ("Ash on his skin and the moon in his hair", "en", ""),
        ("Serpent round his neck, there's a fire in the air", "en", ""),
        ("Three eyes open and the whole world shakes", "en", ""),
        ("Silence on Kailash, every mountain awakes", "en", ""),
        ("He don't need gold, he don't need a throne", "en", ""),
        ("Sitting in the snow, but he's never alone", "en", ""),
        ("Ganga in his locks and the damru in his hand", "en", ""),
        ("One name echoes — Shiva, understand", "en", ""),
    ]),
    ("verse2", "verse", [
        ("शिवाय गौरी वदनाब्ज वृन्द सूर्याय", "dev", "The sun that blooms the lotus face of Gauri"),
        ("दक्षाध्वर नाशकाय", "dev", "Destroyer of Daksha's sacrifice"),
        ("श्री नीलकण्ठाय वृषध्वजाय", "dev", "The blue-throated one, with the bull on his banner"),
        ("तस्मै शिकाराय नमः शिवाय", "dev", "To that 'Shi' — salutations to Shiva"),
        ("वसिष्ठ कुम्भोद्भव गौतमार्य", "dev", "Worshipped by Vasishtha, Agastya and Gautama"),
        ("मुनीन्द्र देवार्चित शेखराय", "dev", "Revered by the great sages and the gods"),
        ("चन्द्रार्क वैश्वानर लोचनाय", "dev", "Whose eyes are the moon, the sun and fire"),
        ("तस्मै वकाराय नमः शिवाय", "dev", "To that 'Va' — salutations to Shiva"),
    ]),
    ("rap2", "rap", [
        ("When the ocean got churned and the poison came out", "en", ""),
        ("Every god ran scared, every heart filled with doubt", "en", ""),
        ("He drank it all down, held it still in his throat", "en", ""),
        ("Neelkanth, blue fire — that's the hope that I quote", "en", ""),
        ("Daksha had the pride but the pride turned to dust", "en", ""),
        ("Tandav on the beat — in Mahadev we trust", "en", ""),
        ("Five sacred letters: Na · Ma · Shi · Va · Ya", "en", ""),
        ("Every breath I take — Om Namah Shivaya", "en", ""),
    ]),
    ("bridge", "bridge", [
        ("ॐ नमः शिवाय", "dev", "Salutations to Shiva"),
        ("हर हर महादेव", "dev", "Hail the Great God"),
    ]),
    ("chorus", "drop", [
        ("यक्षस्वरूपाय जटाधराय", "dev", "Who takes the form of a Yaksha, bearer of matted locks"),
        ("पिनाकहस्ताय सनातनाय", "dev", "Holding the Pinaka bow, the eternal one"),
        ("दिव्याय देवाय दिगम्बराय", "dev", "Divine, the God, clothed by the sky"),
        ("तस्मै यकाराय नमः शिवाय", "dev", "To that 'Ya' — salutations to Shiva"),
        ("पञ्चाक्षरमिदं पुण्यं यः पठेच्छिवसन्निधौ", "dev", "Whoever recites these sacred five syllables near Shiva"),
        ("शिवलोकमवाप्नोति शिवेन सह मोदते", "dev", "Reaches Shiva's realm and rejoices with Him"),
    ]),
    ("outro", "outro", [
        ("नागेन्द्रहाराय त्रिलोचनाय", "dev", "He who wears the king of serpents, the three-eyed one"),
        ("तस्मै नकाराय नमः शिवाय", "dev", "To that 'Na' — salutations to Shiva"),
    ]),
]

# Section start times (seconds) per take, read from the vocal transcription of each take.
# The last section runs to the end of the song. Optional: "drop" = time of the instrumental drop
# (gets its own blazing section), "line_times" = exact (start, end) per line for a section.
TIMINGS = {
    "take1": {"intro": 0.0, "verse1": 18.0, "rap1": 48.0, "verse2": 67.0, "rap2": 84.0,
              "bridge": 97.0, "chorus": 117.0, "outro": 160.0},
    # Take 3 (seed 108): cleanest take. Drums drop out at 1:45 (breakdown), full drop at 2:00.
    "take3": {"intro": 0.0, "verse1": 20.5, "rap1": 56.8, "verse2": 75.5, "rap2": 94.6,
              "bridge": 104.6, "chorus": 144.8, "outro": 173.4,
              "drop": 120.0,
              "line_times": {"intro": [(12.5, 20.2)],
                             "bridge": [(105.0, 119.5), (141.2, 144.6)]}},
}
