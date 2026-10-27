import os, datetime
print("🤖 RIGAN AI - Marima V3 [Na Kumbukumbu]")

if os.path.exists("jina.txt"):
    with open("jina.txt") as f:
        jina = f.read()
    print(f"Karibu tena {jina}! Nilikukumbuka!")
else:
    jina = input("Jina lako halisi? ").strip()
    with open("jina.txt","w") as f:
        f.write(jina)
    print(f"Sawa {jina}, sitakusahau tena!")

while True:
    s = input(f"\n{jina}: ").strip()
    s_low = s.lower()

    if s_low in ["toka","exit","bye","lala"]:
        print(f"Rigan: Baadaye {jina}! Kesho tukiongea nitakukumbuka tu!")
        break
    elif "habari" in s_low:
        print(f"Rigan: Poa sana {jina}! Marima mambo?")
    elif "saa" in s_low:
        print(f"Rigan: Saa ni {datetime.datetime.now().strftime('%H:%M')}")
    elif "wewe ni nani" in s_low:
        print("Rigan: Mimi ni Rigan V3, naishi Termux, nimetengenezwa na wewe!")
    elif "hesabu" in s_low:
        try:
            hes = input("Rigan: Weka hesabu (mf: 5*5+2): ")
            print(f"Rigan: Jibu ni {eval(hes)}")
        except:
            print("Rigan: Hesabu si sawa kaka")
    elif "joke" in s_low or "vichekesho" in s_low:
        print("Rigan: Mwalimu: Kwa nini kuku alivuka barabara? Mwanafunzi: Kufika Marima! 😂")
    else:
        print(f"Rigan: Nimekuelewa {jina} - '{s}'")
