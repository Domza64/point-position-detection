# 📐 PnP Camera Pose Solver - Matematički Vodič i Upute

Ovaj modul (`PnP/pnp_solver.py`) omogućuje izračunavanje točne 3D pozicije i orijentacije kamere (ekstrinzičnih parametara) za datasetove koji ih nemaju (poput `Fountain` i `Statue`), koristeći samo matricu unutarnjih parametara $K$ (koja je definirana u `K.txt`) i najmanje 4 ručno označene korespondencije (veza 2D piksela na slici i 3D točke u prostoru).

---

## 🧠 1. Što se koristi i Zašto?

U računalnom vidu, projekcija 3D točke iz prostora $\mathbf{X}_w = [X, Y, Z]^T$ na 2D koordinatu na senzoru slike $\mathbf{x} = [u, v, 1]^T$ (homogene koordinate) opisuje se jednadžbom:

$$\mathbf{x} \sim K \cdot \left( R \cdot \mathbf{X}_w + T \right)$$

Gdje su:
*   $K$ - **Matrica unutarnjih parametara kamere** (fokusna daljina, optičko središte).
*   $R$ - **Matrica rotacije** ($3 \times 3$) koja rotira točke iz koordinatnog sustava svijeta u sustav kamere.
*   $T$ - **Translacijski vektor** ($3 \times 1$) koji opisuje pomak ishodišta svijeta u koordinatnom sustavu kamere.

Problem procjene $R$ i $T$ iz poznatog $K$ i skupa sparivanja 2D i 3D točaka naziva se **Perspective-n-Point (PnP) problem**. Za rješavanje koristimo:
1.  **OpenCV (`cv2.solvePnP`)**: Industrijski standard za numeričko rješavanje PnP problema iterativnom Levenberg-Marquardt optimizacijom koja minimizira reprojekcijsku pogrešku.
2.  **NumPy**: Za matrične operacije i transformacije koordinatnih sustava.

---

## 🗺️ 2. Transformacija Koordinatnih Sustava

OpenCV i naš Three.js 3D vizualizator koriste različite konvencije za koordinatne sustave. Solver automatski rješava te razlike kroz preciznu matematiku:

### Konvencije:
*   **OpenCV (Sustav Kamere)**: 
    *   $+X_c$ desno
    *   $+Y_c$ dolje (prema dnu slike)
    *   $+Z_c$ naprijed (duž optičke osi, smjer gledanja)
    *   *Sustav je desnoruki.*
*   **Projektni Datasets (Ljevoruki sustav)**:
    *   $+X$ desno
    *   $+Y$ gore
    *   $+Z$ naprijed
    *   *Handedness*: Vektori moraju zadovoljiti $\text{Right} \times \text{Up} = \text{Forward}$.

### Izračun iz OpenCV $R$ i $T$ u parametre vizualizatora:

1.  **Pozicija kamere u svijetu ($C$)**:
    U OpenCV jednadžbi, $T$ je položaj svijeta iz perspektive kamere. Da bismo saznali stvarnu 3D poziciju kamere u koordinatama svijeta ($C$), moramo invertirati transformaciju:
    $$C = -R^T \cdot T$$

2.  **Orijentacijski vektori**:
    Stupci transponirane matrice rotacije $R^T$ predstavljaju smjerove lokalnih osi kamere ($X_c, Y_c, Z_c$) izražene u koordinatama svijeta:
    *   $\mathbf{r}_1 = R^T[:, 0]$ (Lokalna desna os)
    *   $\mathbf{r}_2 = R^T[:, 1]$ (Lokalna donja os)
    *   $\mathbf{r}_3 = R^T[:, 2]$ (Lokalna prednja os / optička os)

    Da bismo dobili vektore u ljevorukoj konvenciji projekta gdje je Y os okrenuta **prema gore**, a Right $\times$ Up = Forward:
    *   **Forward ($F$)**: $\mathbf{r}_3$
    *   **Up ($U$)**: $-\mathbf{r}_2$ (invertiramo Y os jer u OpenCV-u Y ide prema dolje)
    *   **Right ($R_{right}$)**: $-\mathbf{r}_1$ (invertiramo X os kako bismo promijenili orijentaciju sustava u ljevoruku, zadržavajući ortogonalnost)

    > [!NOTE]
    > Ova transformacija osigurava da je $(\text{Right} \times \text{Up}) = (-\mathbf{r}_1) \times (-\mathbf{r}_2) = \mathbf{r}_1 \times \mathbf{r}_2 = \mathbf{r}_3 = \text{Forward}$, što u potpunosti odgovara formatu učitanom iz `boxInput.txt` i `entranceInput.txt`.

---

## 🛠️ 3. Kako Koristiti PnP Solver?

### Korak 1: Prikupljanje korespodencija
Otvorite 3D vizualizator i sliku koju želite kalibrirati (npr. `fountain1.jpg`). Odaberite 4 istaknute i lako prepoznatljive točke na objektu.
Zapišite njihove:
1.  **3D koordinate (X, Y, Z)** iz vizualizatora (možete očitati koordinate prelijetanjem miša ili postavljanjem točaka).
2.  **2D koordinate (u, v)** u pikselima na slici. Koordinata `u` je piksel udaljenost od lijevog ruba slike, a `v` je piksel udaljenost od gornjeg ruba slike.

### Korak 2: Pokretanje u 3DMegaMind orkestratoru
1.  Pokrenite `3DMegaMind.py`.
2.  Odaberite aktivni dataset (npr. opcija **1**, pa izaberite **4** za Fountain).
3.  Odaberite opciju **5 (Izračunaj poziciju kamere iz 2D-3D točaka (PnP Solver))**.
4.  Ako OpenCV i NumPy nisu instalirani, program će ponuditi automatsku instalaciju. Pritisnite `y`.

### Korak 3: Unos podataka u CLI
Program će vas tražiti unos:
1.  **ID kamere / slike** (npr. upišite `1` ako kalibrirate `fountain1.jpg`).
2.  Za svaku od 4 točke unesite redom:
    *   3D koordinate $X, Y, Z$ (npr. `-12.54, 45.12, 110.23`)
    *   2D piksel koordinate $u$ i $v$ (npr. `1520, 850`)

### Korak 4: Automatsko spremanje
Nakon uspješnog izračuna, solver će ispisati dobivenu 3D poziciju i vektore. 
Zatim će vas pitati: `Želite li spremiti ove podatke u input datoteku? (y/n)`.
Odaberite `y` i program će automatski stvoriti ili nadodati kameru u npr. `TestImages/Fountain/fountainInput.txt`.

---

## 🔄 4. Rezultat u Vizualizatoru
Čim se stvori `fountainInput.txt` s novom kamerom, osvježite web stranicu vizualizatora. 
*   U padajućem izborniku kamera pojavit će se novostvorena **Camera 1** (ili bilo koji ID koji ste unijeli).
*   Kada je odaberete, virtualna kamera će skočiti na točno izračunatu poziciju i smjer, a slika `fountain1.jpg` će se preklopiti preko 3D oblaka točaka s točnim FOV-om učitanim iz `K.txt`!
