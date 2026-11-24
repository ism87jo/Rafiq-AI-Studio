from .models import Project


def first_chapter(project_id="bird-that-fell-silent"):
    return Project.model_validate({
        "id": project_id, "title": "نداء الفطرة — الطائر الذي صمت", "style": "3d",
        "script": "معالجة بصرية تجريبية لافتتاح الفصل الأول، مستندة إلى مسودة 19 نوفمبر 2026. أوصاف المظهر والملابس مقترحات قابلة للتعديل، وليست صورًا لأشخاص حقيقيين.\n\nفي فناء البيت عند الغروب، يجلس إسماعيل تحت شجرة. يأتي حمزة يحمل طائره الساكن. يواسيه الأب، ثم ينضم عثمان وصديقه نزار، ويبدأ الحديث عن الحياة.\n\nهذه عينة إنتاج للافتتاح؛ بقية حوار الفصل ستقسم إلى لقطات قصيرة بعد اعتماد شكل الشخصيات والأصوات.",
        "characters": [
            {"id": "ismail", "name": "إسماعيل", "description": "A middle-aged Arab father, warm brown eyes, short dark hair with gray at the temples, neatly trimmed beard, gentle expressive face", "wardrobe": "Olive green long sleeve shirt, dark charcoal trousers", "voice_notes": "صوت أب عربي هادئ ودافئ؛ عينة صوتية مطلوبة"},
            {"id": "hamza", "name": "حمزة", "description": "A young Arab boy, short curly dark hair, large brown eyes, small rounded face", "wardrobe": "Mustard yellow sweater, dark blue trousers, brown shoes", "voice_notes": "صوت شخصية طفل خيالية؛ لا يوجد صوت معتمد بعد"},
            {"id": "othman", "name": "عثمان", "description": "An Arab teenage boy, slim build, short wavy dark hair, curious dark brown eyes", "wardrobe": "Teal blue overshirt over white t-shirt, charcoal jeans, carrying a biology textbook", "voice_notes": "صوت شاب عربي فضولي"},
            {"id": "nizar", "name": "نزار", "description": "An Arab teenage boy, slightly taller than Othman, straight dark hair, thoughtful expression", "wardrobe": "Burgundy sweater, gray trousers", "voice_notes": "صوت شاب عربي متأمل"},
        ],
        "locations": [{"id": "courtyard", "name": "فناء البيت عند الغروب", "description": "A modest Jordanian stone courtyard, one mature tree at the center, wooden bench on the right, teal wooden door at the back left, terracotta pots by the wall, small tea glass on a low table. Warm sunset from camera left. Preserve this spatial arrangement between shots."}],
        "scenes": [
            {"id": "shot-01", "title": "صمت غير مألوف", "prompt": "Wide establishing shot of a quiet courtyard at sunset. Ismail sits under the tree with an untouched glass of tea. The camera slowly pushes inward. Only subtle movement in the leaves. No other characters in frame.", "notes": "اعتماد تكوين الفناء أولًا. لقطة اختبار التوليد الأولى، دون حوار.", "seconds": 5, "seed": 41201, "character_ids": ["ismail"], "location_id": "courtyard"},
            {"id": "shot-02", "title": "حمزة عند الباب", "prompt": "Medium shot at the courtyard door. Hamza walks slowly toward his seated father, gently holding a small motionless bird in both hands. His expression is sad and puzzled. No blood, no injury detail. Slow natural movement.", "notes": "ارفع صورة مرجعية لتركيب الشخصيتين قبل تحويل الوضع إلى صورة إلى فيديو.", "seconds": 5, "seed": 41202, "character_ids": ["ismail", "hamza"], "location_id": "courtyard"},
            {"id": "shot-03", "title": "العصفور لا يتحرك", "prompt": "Close-up of Hamza holding the motionless bird. He looks up toward his father just outside frame. Gentle camera push-in, tender emotion, soft shallow depth of field. The bird remains still.", "notes": "الحوار يضاف كمسار صوتي مستقل؛ مزامنة الشفاه مرحلة لاحقة.", "seconds": 8, "seed": 41203, "character_ids": ["hamza"], "location_id": "courtyard", "dialogue": [{"character_id": "hamza", "text": "أبي، عصفوري لا يتحرك. وضعته قرب الطعام، وناديته كما أفعل كل يوم، لكنه لم يغرد."}]},
            {"id": "shot-04", "title": "جواب الأب", "prompt": "Medium close-up of Ismail kneeling to Hamza's eye level. He looks at his son with compassion, gently placing one hand near the boy's shoulder. Keep the same clothing, tree position and sunset direction.", "seconds": 5, "seed": 41204, "character_ids": ["ismail", "hamza"], "location_id": "courtyard", "dialogue": [{"character_id": "ismail", "text": "أخشى يا بني أن عصفورك قد مات."}]},
            {"id": "shot-05", "title": "عثمان ونزار", "prompt": "Medium two-shot. Othman steps into the courtyard with his friend Nizar. Othman holds an open biology textbook. They look toward Ismail and Hamza, concerned and curious. A slow lateral camera move preserves the established courtyard geography.", "seconds": 5, "seed": 41205, "character_ids": ["othman", "nizar"], "location_id": "courtyard", "dialogue": [{"character_id": "othman", "text": "ما بال حمزة؟"}]},
            {"id": "shot-06", "title": "بداية السؤال", "prompt": "Wide shot of the four characters gathered under the same courtyard tree. Othman sits by his younger brother Hamza, Nizar leans forward thoughtfully, Ismail listens calmly. A quiet cinematic pause as sunset fades. Preserve all four designs and clothing.", "notes": "لقطة جماعية صعبة؛ تأتي بعد نجاح اختبارات شخصية واحدة وشخصيتين.", "seconds": 5, "seed": 41206, "character_ids": ["ismail", "hamza", "othman", "nizar"], "location_id": "courtyard"},
        ],
    })



def interview_project(project_id):
    turns = [
        ("host", "الافتتاح / Opening", "أهلًا بكم. كيف يبدأ المسافر الاستعداد لرحلة الحج؟", 6),
        ("guest", "الإجابة / Answer", "يبدأ بالاطلاع على الشروط الرسمية ومراجعة الوثائق والخدمات قبل اختيار البرنامج.", 9),
        ("host", "الختام / Closing", "شكرًا لك. راجعوا المعلومات الرسمية واكتبوا لنا أسئلتكم.", 6),
    ]
    return Project.model_validate({
        "id": project_id,
        "title": "Rafiq AI Interview Studio — مقابلة جديدة",
        "style": "realistic",
        "script": "مسودة بودكاست مصوّر عن الاستعداد للحج. عدّل الحوار وضع صورة لكل متحدث، ثم أرفق الصوت واستمع إليه واضبط زمن اللقطة قبل التصدير.",
        "characters": [
            {"id": "host", "name": "المقدّم / Host"},
            {"id": "guest", "name": "الضيف / Guest"},
        ],
        "scenes": [
            {
                "id": f"turn-{index}",
                "title": title,
                "seconds": seconds,
                "use_still": True,
                "character_ids": [speaker],
                "dialogue": [{"character_id": speaker, "text": line, "language": "ar"}],
            }
            for index, (speaker, title, line, seconds) in enumerate(turns, 1)
        ],
        "settings": {"width": 1280, "height": 704, "fps": 24},
    })
