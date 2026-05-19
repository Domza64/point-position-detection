# STEM Games 2026 – Dokumentacija razvoja projekta
### 3D Rekonstrukcija oblaka točaka iz stereo slika

---

## 1. Uvod i razumijevanje problema

Kad smo dobili zadatak, cilj je bio jasan ali tehnički izazovan: iz više fotografija istog objekta snimljenih iz različitih kutova rekonstruirati 3D oblak točaka (point cloud). Imali smo 4 dataseta:

| Dataset | Poznate koordinate kamera? | Rezolucija | Napomena |
|---|---|---|---|
| **Box** | ✅ Da | 1920 × 1080 | Kamera FOV 90° |
| **Entrance** | ✅ Da | 1920 × 1080 | Kamera FOV 90° |
| **Statue** | ❌ Ne | varijabilno | FOV 90° |
| **Fountain** | ❌ Ne | 3072 × 2048 | FOV ~84° |

Za **Box** i **Entrance** imali smo `.txt` datoteke s egzaktnim pozicijama kamera (`CamPosition`, `CamForward`, `CamRight`, `CamUp`). Za **Statue** i **Fountain** kamera je bila potpuno nepoznata – puno teži problem.

---

## 2. Razumijevanje geometrije kamera i zraka

### 2.1 Jednadžba zrake iz piksela

Zadatak nam je u uputama dao C++ kod funkcije `GetLineEquation()`, koji smo trebali razumjeti i portirati u Python. Formula je:

```
coeffRight = 2.0 * (pixelCol - resX/2.0 + 0.5) / resX
coeffUp    = -2.0 * (pixelRow - resY/2.0 + 0.5) / resY * (resY / resX)
Direction  = CamForward + coeffRight * CamRight + coeffUp * CamUp
```

Ovo je projekcija piksela iz 2D prostora slike u 3D smjerni vektor. Za svaki piksel dobivamo zraku koja prolazi kroz položaj kamere i tu točku u 3D prostoru. Za FOV od 90°, skala je `tan(45°) = 1.0`. Za Fountain s FOV-om od 84° koristili smo `tan(42°) ≈ 0.9004`.

Python implementacija završila je u `triangulate.py`:

```python
def get_line_equation(pixel_row, pixel_col, res_x, res_y, cam, fov_scale=1.0):
    coeff_right = 2.0 * (pixel_col - res_x / 2.0 + 0.5) / res_x
    coeff_up = -2.0 * (pixel_row - res_y / 2.0 + 0.5) / res_y
    coeff_up = coeff_up * res_y / res_x
    coeff_right *= fov_scale
    coeff_up *= fov_scale
    direction = cam_fwd + coeff_right * cam_rgt + coeff_up * cam_up
    direction = direction / np.linalg.norm(direction)
    return cam_pos, direction
```

---

## 3. Matematika triangulacije: Presjecište dviju 3D zraka

Srce cijelog projekta je geometrija: dvije zrake iz dvije kamere koje gledaju u istu točku u prostoru ne moraju se **točno** sjeći (zbog numeričkih grešaka i šuma u detekciji). Koristio sam metodu **minimalne distance između dviju pravaca u 3D** (closest point approach):

```
Zraka 1: Q = p1 + t1 * d1
Zraka 2: Q = p2 + t2 * d2

Minimum udaljenosti: rijesi sustav za t1 i t2
Točka: midpoint( p1 + t1*d1, p2 + t2*d2 )
Greška: || q1 - q2 ||
```

Implementacija u `triangulate.py` (funkcija `triangulate_rays`) rješava linearni sustav 2×2 i vraća midpoint kao procijenjenu 3D poziciju točke, zajedno s greškom presjecišta.

---

## 4. Detekcija značajki: SIFT

Da bismo uparili piksele između dviju slika iste scene, koristili smo **SIFT (Scale-Invariant Feature Transform)** algoritam iz OpenCV knjižnice. SIFT pronalazi karakteristične točke (uglovi, rubovi) u slici i opisuje ih vektorom od 128 dimenzija neovisnim o rotaciji i skali.

### Lowe's Ratio Test

Za filtriranje lažnih uparivanja koristili smo **Lowe's ratio test**: za svaku značajku tražimo 2 najbliža susjedna deskriptora i zadržavamo uparivanje samo ako je:

```
distance(m1) < ratio * distance(m2)
```

gdje niži ratio znači stroži filtar. Inicijalno smo koristili `ratio = 0.75`.

---

## 5. Transformacija 3D objekta (Fountain / objekt.csv)

U jednoj fazi rada analizirali smo zasebni oblak točaka u datoteci `objekt.csv` (~14,000 točaka iz Fountain dataseta). Objekt je bio **nagnut prema naprijed** (kao boca koja je pala glavom prema naprijed).

### Pristup: Homogena matrica transformacije 4×4

Implementirali smo skriptu `transform.py` koja:

1. **Učitava `objekt.csv`** (stupci X, Y, Z)
2. **Izračunava centroid** oblaka točaka
3. **Primjenjuje rotacijski matricu** za 90° oko X osi:
   ```
   R_x(90°) = [[1, 0,  0],
                [0, 0, -1],
                [0, 1,  0]]
   ```
4. **Formira 4×4 homogenu transformacijsku matricu** H:
   ```
   H = | R  |  t  |
       | 0  |  1  |
   ```
5. **Sprema rezultat** u `transformirani_objekt.csv`

### Problemi i iteracije

- **Prva rotacija** (`+90° oko X`) uspravila je objekt, ali bio je previše nagnute osi.
- Probali smo **rotaciju oko Z osi za 180°** kako bismo ispravili gornju/donju os – to je bolje funkcioniralo.
- Na kraju smo implementirali **interaktivni vizualizator** u Pythonu (`matplotlib`) koji je omogućio ručnu rotaciju za 90° u svim smjerovima (X, Y, Z) tipkama na tipkovnici, bez trajnih promjena CSV-a dok korisnik ne bude zadovoljan.

---

## 6. Fontana (Fountain) – prerada CSV-a

Jedan od prvih konkretnih zadataka je bio **priprema `fountain.csv`** za vizualizaciju. Originalna datoteka imala je vrijednosti u nekim neočekivanim razmjerima.

- Najprije smo greškom sve koordinate **pomnožili sa 1000** – što je rezultiralo ogromnim oblačnim poljem bez smisla.
- Korigirali smo na **množenje sa 100**, što je dalo smislene koordinate u prostoru.

---

## 7. Vizualizator (web aplikacija)

Napravili smo kompletan **web-based 3D vizualizator** u `Visualizer/` direktoriju:

- **Backend:** Python HTTP server (`server.py`) koji servira:
  - Statičke HTML/CSS/JS datoteke
  - `/api/datasets` – lista datasetova
  - `/api/dataset/<name>/cameras` – pozicije i smjerovi kamera
  - `/api/dataset/<name>/points` – oblak točaka u binarnom formatu
  - `/images/<dataset>/<file>` – originalne slike
  
- **Frontend:** Three.js za renderiranje oblaka točaka u browseru, s:
  - Orbitalnom navigacijom (mišem i dodirom)
  - Prikazom kamera u prostoru (strelice smjera, konusi vidnog polja)
  - Kontrolom veličine i prozirnosti točaka
  - Prebacivanjem između datasetova

- **Caching:** Server automatski kompajlira CSV u binarni format (`.bin`, packed `float32 + RGBA bytes`) za brže učitavanje u browser. Ako je CSV noviji od `.bin`, server ga automatski rekompajlira.

- **Konfiguracija** (`config.txt`): Svaki dataset ima vlastitu konfigurabilnu putanju do CSV-a:
  ```ini
  box_csv_path = TestImages/Box/box.csv
  entrance_csv_path = TestImages/Entrance/entrance.csv
  ```

---

## 8. Triangulacija za Box i Entrance (poznate kamere)

### 8.1 Pokušaj: Kollegin repozitorij za Checkerboard + PnP

Prije nego smo krenuli na direktnu triangulaciju, pokušali smo iskoristiti repozitorij koji je napravio kolega iz tima. Njegova ideja je bila:

1. **Detekcija checkerboard uzorka** (2×2 kvadrata) na pozadini scene u svakoj slici
2. **Izračun 3D pozicija kutnih točaka** checkerboarda (poznate su u world koordinatama)
3. **PnP Solver** (Perspective-n-Point) – korištenjem tih 3D-2D korespondencija procjeniti egzaktnu poziciju i orijentaciju svake kamere
4. S poznatim kamerama → primijeniti isti triangulacijski pipeline kao za Box/Entrance

Zamisao je bila elegantna – checkerboard daje pouzdane 3D reperne točke iz kojih PnP može rekonstruirati kamere automatski, bez ručnog unosa.

**Zašto nije radilo:**
- Repozitorij nije bio kompatibilan s našim koordinatnim sustavom i formatom ulaznih podataka
- Detekcija checkerboarda nije bila dovoljno pouzdana u svim slikama (varijabilno osvjetljenje, perspektivna distorzija)
- Nismo imali dovoljno vremena za debugging i integraciju tuđeg koda u naš pipeline

Nakon što ovaj pristup nije dao rezultate, **odlučili smo za jednostavniju ali pouzdaniju triangulaciju** – direktno iz poznatih koordinata kamera koje su nam bile dane u `.txt` datotekama.

### 8.2 Inicijalni pipeline

Napisali smo `triangulate.py` kao glavnu skriptu. Inicijalni pipeline:

1. **Učitaj kamere** iz `boxInput.txt` / `entranceInput.txt`
2. **Učitaj slike** i poveži ih s ID-evima kamera
3. **SIFT detekcija** na svakoj slici
4. **Uparivanje svih parova kamera** (brute-force matching)
5. **Lowe's ratio test** (filtriranje lažnih uparivanja)
6. **RANSAC + Fundamentalna matrica** (epipolarno ograničenje – odbacivanje outliera)
7. **Triangulacija** svake uparene točke
8. **Filtriranje po grešci** triangulacije
9. **Photo-consistency check** (provjera boje u trećim kamerama)
10. **SOR (Statistical Outlier Removal)** – čišćenje izoliranih točaka
11. **Zapis u CSV**

### 8.3 Problem: premalo točaka

Inicijalni run za **Box** dao je samo oko ~16,000 točaka. Problem je bio višestruk:

**Prestrogi SIFT parametri:**  
- `nfeatures=15000` – premalo za površine s malo teksture
- `contrastThreshold=0.01` – odbacivao je mnoge značajke na ravnim površinama kocke

**Prestrogi ratio test:**  
- `ratio=0.75` – odbacivalo previše valjanih uparivanja

**Photo-consistency provjera:**  
- Logika je odbacivala točke na bokovima kocke jer su bile okluzijom skrivene s većine ostalih kamera (bile su vidljive samo iz 1-2 kuta)
- Uvjet `ratio >= 0.3` (30% kamera mora potvrditi boju) bio je prestrogo za objekt s vidljivim okluzijama

### 8.4 Rješenje: adaptivni parametri po datasetu

Implementirali smo **per-dataset prilagodbu parametara**:

```python
if dataset_name.lower() in ["box", "entrance"]:
    sift = cv2.SIFT_create(nfeatures=40000,
                           contrastThreshold=0.005,
                           edgeThreshold=30)
    ratio_thresh = 0.82
    ransac_thresh = 1.5
    max_err_base = 1.5
    max_err_ratio = 0.02
```

Za Box i Entrance **isključili smo photo-consistency provjeru** jer su oba objekta s vidljivim okluzijama:

```python
passed_consistency = True
if dataset_name.lower() not in ["box", "entrance"]:
    passed_consistency = check_photo_consistency(...)
```

SOR filtar smo ublažili s faktora `1.2` na `1.5` standardnih devijacija:
```python
sor_factor = 1.5 if dataset_name.lower() in ["box", "entrance"] else 1.2
```

### 8.5 Rezultati

| Dataset | Prije optimizacije | Nakon optimizacije | Poboljšanje |
|---|---|---|---|
| **Box** | ~16,000 točaka | **46,725 točaka** | **~3× više** |
| **Entrance** | ~32,037 točaka | **64,597 točaka** | **~2× više** |

---

## 9. Fountain i Statue (nepoznate kamere)

Za datasete bez poznatih pozicija kamera, problem je bio puno teži jer smo imali **potpuno nepoznate egzogene parametre** (pozicija + orijentacija svake kamere).

### 9.1 Pokušaj: ručno pogađanje kamera

Razmatrali smo ručnu procjenu pozicija kamera na temelju vizualnog pregleda scena. Ovo je bilo jako nepouzdano i vremenski iznimno zahtjevno.

### 9.2 Pokušaj: OpenCV SfM modul

Pokušali smo koristiti OpenCV-ov `sfm` modul koji implementira Bundling Adjustment i rekonstrukciju scene. Problem je bio što `opencv-contrib` modul s SfM podrškom zahtijeva posebnu kompilaciju koja nije bila dostupna u standardnoj instalaciji.

### 9.3 Pokušaj: PnP pristup uz checkerboard repo (custom ručno kodirano rješenje)

Kao što je opisano u sekciji 8.1, pokušali smo i ovdje iskoristiti PnP solver temeljen na detekciji checkerboarda. Cilj je bio automatski rekonstruirati pozicije kamera bez ručnog unosa, pa onda primijeniti triangulaciju. Ovaj pristup nije dao upotrebljive rezultate.

### 9.4 Rješenje: COLMAP

Na kraju smo uspješno koristili **COLMAP** (Computerized Optical LAyout MAPping) – industrijski standard za Structure-from-Motion (SfM) koji iz skupa fotografija automatski:

1. **Detektira i uparuje značajke** između svih parova slika (SIFT u pozadini)
2. **Procjenjuje pozicije i orijentacije kamera** (egzogeni parametri) i intrinsične parametre
3. **Generira rijedak oblak točaka** (Sparse Reconstruction)
4. **Generira gust oblak točaka** (Dense Reconstruction via MVS – Multi-View Stereo)

COLMAP je za **Fountain** i **Statue** datasete generirao oblake točaka koji su nam poslužili kao konačni ulazni podaci za vizualizator. Izlazni podaci iz COLMAP-a dolaze u specifičnom formatu koji sadrži više informacija nego što nam je potrebno – pozicije kamera, normali površina, vidljivosti točaka itd.

**Format COLMAP izlaza koji smo koristili:**  
COLMAP izvozi point cloud u `.ply` ili tekstualni format koji između ostalog sadrži `X, Y, Z, R, G, B` koordinate i boje svake točke, ali i mnoge dodatne metapodatke.

---

## 10. Point Cloud Completer

Razvili smo `Completer/completer.py` – modul za **zgušnjavanje oblaka točaka** koji uzima rijedak oblak i pokušava interpolirati nove točke između postojećih.

Tehnika je **lokalna interpolacija površine** (Local Surface Interpolation):

```python
def local_surface_interpolation(self, df, k=6, min_dist=8.0, max_dist=35.0):
    # Za svaku točku: nađi k najbližih susjeda
    # Za svaki par (točka, sused): interpoliraj novu točku na sredini segmenta
    # Boja: interpolacija boja krajnjih točaka
```

Koristili smo **cKDTree** (scipy) za učinkovito pretraživanje susjeda u 3D prostoru umjesto naivnog O(n²) przimjeravanja.

Dodali smo i **Radius Outlier Removal (ROR)** koji uklanja točke s manje od `min_neighbors` susjeda u radijusu `R`:

```python
def apply_radius_outlier_removal(self, df, radius, min_neighbors):
    tree = cKDTree(xyz)
    indices_list = tree.query_ball_point(xyz, r=radius)
    mask = [len(indices) >= min_neighbors for indices in indices_list]
```

Completer je integriran u **`3DMegaMind.py`** – main launcher skriptu koja:
1. Pokreće triangulaciju
2. Primjenjuje Completer
3. Ažurira Visualizer config i pokreće server

---

## 11. Algoritmi – sažetak

| Algoritam | Namjena | Biblioteka |
|---|---|---|
| **SIFT** | Detekcija značajki otpornih na rotaciju i skalu | OpenCV |
| **Brute-Force Matching** | Uparivanje SIFT deskriptora između parova slika | OpenCV |
| **Lowe's Ratio Test** | Filtriranje dvosmislenih / lažnih uparivanja | Ručna implementacija |
| **RANSAC + Fundamental Matrix** | Epipolarno filtriranje – odbacivanje outliera koji krše geometriju | OpenCV |
| **Ray-Ray Triangulation** | Rekonstrukcija 3D točke iz dviju 3D zraka | Ručna implementacija (NumPy) |
| **Photo-Consistency Check** | Provjera boje točke u trećim kamerama (reprojection) | Ručna implementacija |
| **SOR (Statistical Outlier Removal)** | Uklanjanje izoliranih outlier točaka | scipy.spatial.cKDTree |
| **ROR (Radius Outlier Removal)** | Uklanjanje točaka s malo susjeda | scipy.spatial.cKDTree |
| **Local Surface Interpolation** | Zgušnjavanje oblaka točaka interpolacijom | scipy.spatial.cKDTree |
| **Homogena matrica transformacije** | Rotacija i translacija oblaka točaka | NumPy |
| **PnP (Perspective-n-Point)** | Procjena pozicije kamere iz 3D-2D korespondencija (pokušaj) | OpenCV |

---

## 12. Struktura projekta

```
zzStemGames2026_ProjectTask/
│
├── 3DMegaMind/                      ← SVE AKTIVNO KORIŠTENO
│   ├── 3DMegaMind.py                # Master launcher: izbornik, server, completion
│   ├── triangulate.py               # Triangulacija za Box i Entrance
│   ├── DOKUMENTACIJA.md             # Ova dokumentacija
│   ├── STEM_Games_2026__Project.pdf # Originalni zadatak
│   ├── project_text.txt             # Tekst zadatka
│   │
│   ├── Completer/
│   │   └── completer.py             # Modul za zgušnjavanje oblaka točaka
│   │
│   ├── PnP/
│   │   ├── pnp_solver.py            # PnP solver (opcija 5 u izborniku)
│   │   └── pnp_documentation.md
│   │
│   ├── Visualizer/
│   │   ├── server.py                # Python HTTP server za web vizualizator
│   │   ├── config.txt               # Putanje do CSV datoteka po datasetu
│   │   └── static/                  # HTML, CSS, JS frontend (Three.js)
│   │
│   └── TestImages/
│       ├── Box/
│       │   ├── box1.png ... box12.png
│       │   ├── boxInput.txt         # Koordinate 12 kamera
│       │   └── box.csv              # Oblak točaka – triangulacija (46,725 točaka)
│       ├── Entrance/
│       │   ├── entrance1.png ... entrance12.png
│       │   ├── entranceInput.txt
│       │   └── entrance.csv         # Oblak točaka – triangulacija (64,597 točaka)
│       ├── Statue/
│       │   ├── statue*.jpg
│       │   └── statue.csv           # Oblak točaka – COLMAP
│       └── Fountain/
│           ├── fountain*.jpg
│           └── fountain.csv         # Oblak točaka – COLMAP
│
└── SMECE/                           ← EKSPERIMENTALNI / NEKORIŠTEN KOD
    ├── debug_triangulation.py
    ├── find_centers.py
    ├── solve_consistent_pnp.py
    ├── test_pnp_on_box.py
    ├── transform.py / transform_final.py
    ├── generate_coco.py
    ├── objekt.csv
    ├── Visualizer.zip
    └── point-position-detection/    ← Kollegin repo (checkerboard detekcija)
```

---

## 13. Ključne lekcije i zaključak

### Što je dobro funkcioniralo:
- **SIFT + RANSAC + Triangulacija** je bio solidan temelj za datasete s poznatim kamerama
- **Adaptivni parametri** po datasetu su drastično poboljšali broj točaka
- **Isključivanje photo-consistency provjere** za objekte s jakim okluzijama pokazalo se ključnim
- **Binarne cache datoteke** za vizualizator znatno su ubrzale učitavanje u browser

### Što je bilo izazovno:
- **Dataseti bez poznatih kamera** (Fountain, Statue) su bili puno teži – nismo uspjeli automatski rekonstruirati pozicije kamera bez COLMAP-a ili sličnog alata
- **Photo-consistency** je lijepa ideja u teoriji, ali u praksi na okluzivnim objektima radi kontraproduktivno
- **Drift kod PnP-a** – greška se akumulirala kroz iterativno dodavanje kamera jer nismo imali globalni Bundle Adjustment

### Daljnji razvoj – Plan za budućnost

Nakon iskustva s ovim projektom, jasno nam je koji je najrobustniji i najefikasniji put za rekonstrukciju 3D scene:

#### Korak 1 – COLMAP za sve datasete

Koristiti **COLMAP** kao primarni alat za rekonstrukciju oblaka točaka za **sve** datasete (Box, Entrance, Statue, Fountain). COLMAP automatski rješava i problem nepoznatih kamera (SfM faza) i generira gust oblak točaka (MVS faza) bez ikakve ručne intervencije.

#### Korak 2 – Filtriranje i ekstrakcija relevantnih podataka

COLMAP-ov izlaz sadrži mnogo više informacija nego što nam treba:
- Pozicije i rotacije kamera
- Normali površina točaka
- Informacije o vidljivosti (u kojim kamerama je točka vidljiva)
- Razne metapodatke o rekonstrukciji

Potrebno je **filtrirati te podatke** i zadržati samo ono što nam je bitno:

```
X, Y, Z   ← 3D koordinata točke u prostoru
R, G, B   ← boja točke uzorkovana iz originalne slike
```

#### Korak 3 – Standardizirani CSV format

Sve filtrirane podatke upisati u naš **standardizirani CSV format**:

```csv
X,Y,Z,R,G,B
12.340,-5.670,110.230,255,128,64
...
```

**Zašto CSV?**  
CSV je odabran kao format pohrane jer je:
- **Najbrži za čitanje i pisanje** u Pythonu (pandas `read_csv` / `to_csv`)
- **Najlakši za pregled** – može se otvoriti u bilo kojem tekst editoru ili Excelu
- **Kompaktan i human-readable** – lako je debugirati i vizualno provjeriti podatke
- **Univerzalno kompatibilan** – rade s njim svi naši alati (Visualizer, Completer, triangulate.py)

Svaka CSV datoteka predstavlja **jedan objekt/scenu** dobivenu iz skupa slika. Ovo nam omogućava modularan pristup – svaki dataset je zasebna, prenosiva datoteka.

#### Korak 4 – Automatska integracija u Visualizer

Visualizator je već konfiguriran da automatski učita novu CSV datoteku čim se ažurira (`config.txt` → path → auto-recompile u `.bin`). Cijeli workflow bi bio:

```
Slike → COLMAP → filtriranje → CSV → Visualizer
```

---

*Dokumentacija napisana 19. svibnja 2026. kao dio STEM Games 2026 natjecanja – Technology Arena.*
