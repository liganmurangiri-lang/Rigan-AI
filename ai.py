import random

print("KARIBU KWENYE REAGAN AI")

while True:
    swali = input("Wewe: ").lower()

    if "habari" in swali:
        print("Reagan AI: Nzuri sana!")

    elif "jina" in swali:
        print("Reagan AI: Mimi ni Reagan AI.")

    elif "asante" in swali:
        print("Reagan AI: Karibu sana!")

    elif "toka" in swali:
        print("Reagan AI: Kwaheri!")
        break

    else:
        print("Reagan AI: Bado sijajifunza hilo.")
