# Triangulacija

## Što je to?
Kad smo napokon skužili koje su točke koje na slikama (to iz 2D detekcije), morali smo nekako naći njihovu stvarnu poziciju u 3D prostoru.

## Kako to radimo?
Za svaku sliku imamo podatke o kameri - gdje se točno nalazi i u kojem smjeru gleda.
- Za svaku uparenu 2D točku bacamo zraku (*ray*) iz kamere u tom smjeru.
- Tamo gdje se zrake iz različitih slika i kamera presijecaju, tamo bi trebala biti 3D pozicija markera.
- Naravno da se u praksi zrake nikad ne pogode točno u milimetar zbog grešaka u detekciji, pa provlačimo neku aproksimaciju i tražimo točku na kojoj nam je najmanja greška između tih zraka.
