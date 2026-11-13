# MARS SURVIVE 360 — loyiha tavsifi va ilmiy to‘g‘rilik bahosi

NASA Space Apps 2026 · *Interplanetary Survival Guide: Martian Map* · Hudud: Jezero krateri

> Bu qarorlarni qo‘llab-quvvatlash va o‘qitish uchun prototip. Modellar soddalashtirilgan va bu ochiq
> ko‘rsatilgan. Natijalar astronavtlar xavfsizligi bo‘yicha tavsiya **emas**.

---

## A qism — Tashkilotchilarning to‘rt savoli

### 1. Mahsulot qanday muammoni hal qiladi?
NASA vositalari (JPL Mars Trek, USGS geologik xaritalari) ma’lumotlarni Marsning **mintaqaviy va global**
xaritalari ustiga qo‘yish imkonini beradi. Lekin sirtga chiqish bir necha kilometr va bir necha soat
miqyosida rejalashtiriladi, va ekipaj quyidagi savollarga javob berishi kerak:
- qaysi yo‘ldan boramiz;
- u yerda nimani ko‘ramiz;
- kislorod va energiya yetadimi;
- har doim qaytib kela olamizmi va qachon ortga burilish kerak;
- aloqa ishlaydimi;
- bugun Quyosh tinchmi.

MARS SURVIVE 360 bu javoblarni bitta joy — Jezero krateri uchun bitta vositada jamlaydi:
- relyef va xavflar;
- to‘rtta muqobil marshrut;
- har bir marshrut bo‘yicha resurslar sarfi;
- oxirgi xavfsiz qaytish nuqtasi;
- GPS siz navigatsiya aniqligi;
- aloqa va relay qamrovi;
- kosmik ob-havo;
- Perseverance roveri har bir nuqtada nimani ko‘rgani;
- xavf matritsasi, favqulodda holatlar simulyatsiyasi va eksport qilinadigan hisobot.

### 2. Qaysi haqiqiy NASA ma’lumotlari ishlatilgan?

| NASA / USGS manbasi | Qanday ishlatiladi | Topshirilayotgan versiyadagi holati |
|---|---|---|
| USGS Astrogeology: **Jezero uchun Mars 2020 CTX DEM mozaikasi** (20 m/piksel) | Balandlik → qiyalik, g‘adir-budurlik, xavflar, marshrutlar, 3D | Yuklab olish va qayta ishlash tayyor. NASA serverlari yig‘ish kompyuteridan ochilmadi, shuning uchun testlar foydalanuvchi haqiqiysini yuklab olguncha aniq belgilangan **SYNTHETIC DEM** da bajarilgan. |
| **NASA JPL Mars Trek** WMTS: Viking MDIM 2.1 rangli mozaikasi va MGS MOLA soyali relyefi | Optik va topografik asos xaritalar | Plitkalarni brauzer o‘zi yuklaydi. |
| **NASA DONKI** (chaqnashlar, SEP, Marsga yetib kelish WSA-ENLIL prognozli CME, bo‘ronlar) | Chiqishning radiatsiya belgisi; xavf matritsasiga uzatiladi | Onlayn mijoz tayyor, api.nasa.gov kaliti bilan ishlaydi. |
| **Perseverance izi** (NASA/JPL MMGIS M20 GeoJSON) | Ishonchli dalil: marshrutning rover haqiqatda yurgan relyefga yaqinligi | Onlayn mijoz tayyor; saqlangan faylni ham yuklash mumkin. |
| **Perseverance xom tasvirlari** (mars.nasa.gov lentasi) | Marshrut nuqtalarida «astronavt nimani ko‘radi» | Onlayn mijoz tayyor. |
| **Curiosity RAD** sirt dozasi (Hassler va boshq. 2014) | Bazaviy radiatsiya dozasi | E’lon qilingan qiymat. |
| **NASA GISS Mars24** algoritmi (Allison & McEwen 2000) | Mars vaqti, fasl, Quyosh balandligi | Maqoladagi misol bo‘yicha tekshirilgan. |
| **NAIF SPICE** yadrolari (LSK, PCK, SPK) | Quyosh geometriyasini qo‘shimcha tekshirish | Ixtiyoriy; foydalanuvchi yadro fayllarini qo‘shsa ishlatiladi. |
| **Perseverance MEDA** formati | Ob-havo tahlili | MEDA formatidagi CSV qabul qilinadi; ichki namuna sintetik. |
| **THEMIS** kunduzgi IQ mozaikasi | Issiqlik qatlami | Ixtiyoriy. |

Chellenj kamida uch turdagi ma’lumotni talab qiladi. Bu versiya quyidagilarni qamraydi:
- **topografik** (DEM, MOLA);
- **optik** (Viking mozaikasi, rover tasvirlari);
- **radiatsiya va kosmik ob-havo** (RAD dozasi, DONKI);
- **atmosfera** (MEDA);
- **issiqlik** (THEMIS, ixtiyoriy).

Interfeysdagi har bir natija belgi bilan ko‘rsatiladi: **Haqiqiy**, **Sintetik**, **Simulyatsiya** yoki
**Foydalanuvchi**.

### 3. Yechimning farqi nimada?
1. **Avvalo omon qolish, shunchaki xarita emas.** Har bir marshrut ekipaj qaytib kela oladimi, degan savol
   bilan baholanadi. Har bir marshrut uchun ilova hisoblaydi:
   - marshrut bo‘ylab kislorod va energiya;
   - *omon qolish chegarasi*: yo‘lga ketgan vaqt va eng tez qaytish vaqti;
   - **oxirgi xavfsiz qaytish nuqtasi**.
2. **Rejalashtiruvchi ichidagi o‘qituvchili ML-model.** O‘tish imkoniyati klassifikatori o‘qitishda ko‘rmagan
   xarita bloklarida boshqa ikki model bilan solishtiriladi:
   - modellar: logistik regressiya, gradiyent bustingi va PyTorch neyron tarmog‘i;
   - ko‘rsatkichlar: precision, recall, F1, ROC-AUC va PR-AUC.

   Uning ehtimollik xaritasi to‘g‘ridan-to‘g‘ri marshrut narxiga kiradi. Model va uning zaif tomonlari model
   kartasida yozilgan.
3. **Sayyoradan kraterga.** Haqiqiy NASA tasviri (Viking rangli mozaikasi, ilovaga joylangan, shuning uchun har
   doim ochiladi) bilan aylantiriladigan 3D Mars globusi Jezero, Perseverance va Curiosity ni ko‘rsatadi; bir bosish
   kraterga yaqinlashtiradi va marshrutlar bilan mahalliy 3D relyefni ochadi.
4. **Haqiqiy roverdan ishonchli dalil.** Marshrutlar Perseverance ning haqiqiy yo‘li bilan solishtiriladi,
   eng yaqin solning xom tasvirlari esa ekipajga joy qanday ko‘rinishini ko‘rsatadi.
5. **«Chiqish / chiqmaslik» qarorida kosmik ob-havo.** DONKI hodisalari, jumladan Marsga yetib kelishi prognoz
   qilingan CME, xavf matritsasidagi radiatsiya xavfini oshiradi.
6. **Halollik — asosiy tamoyil.** Ma’lumot sinflari hamma joyda ko‘rsatiladi. Haqiqiy ma’lumot yuklanmaguncha
   **SYNTHETIC DEM** belgisi turadi, va hech bir sintetik raqam Mars o‘lchovi sifatida ko‘rsatilmaydi.
7. **Jamoa uchun qulay.**
   - 27 ta ishlaydigan modul, REST API va 18 ta interfeys tili, jumladan o‘ngdan chapga yoziladigan arab tili.
   - PDF, HTML, CSV, JSON va Excel hisobotlari.
   - Mars koordinata tizimi IAU_2015:49900 dagi GIS GeoPackage.
   - Windows va Linux uchun bir bosishda ishga tushirish skriptlari.
   - 184 ta avtomatik test, barchasi o‘tadi.

### 4. Mahsulot kelajakdagi Mars tadqiqotchilariga qanday yordam beradi?
- **Chiqishdan oldin (yashash modulida):**
  - aniq afzallik va kamchiliklari ko‘rsatilgan to‘rt variantdan marshrut tanlash;
  - qaytish vaqtini va kislorod zaxirasini ko‘rish;
  - aloqa soyalari va relay oynalarini tekshirish;
  - kosmik ob-havo belgisini o‘qish;
  - boriladigan joylarning haqiqiy rover tasvirlarini ko‘rish.
- **Mashq:** favqulodda ssenariylarni (kislorod sizishi, quvvat yo‘qolishi, aloqa uzilishi, navigatsiya
  og‘ishi, to‘siqni aylanib o‘tish) o‘tkazib, chiqishni bekor qilish qarorini va zaxiralarni ko‘rish.
- **Ilm-fan:** ilmiy maqsadlarni marshrutga bog‘lash va kuzatuv vazifalarini yaratish.
- **Haqiqiy ma’lumot kelgach:** ML-modelni haqiqiy DEM da bir bosishda qayta o‘qitish. Keyin xuddi shu kod DEM
  mavjud bo‘lgan har qanday boshqa qo‘nish joyi uchun ishlaydi.

---

## B qism — Ilmiy to‘g‘rilik bahosi

**Xulosa.** Geometriya, vaqt hisobi va radiofizika standart va tekshirilgan. Fiziologik, rover va radiatsiya
modellari birinchi tartibli yaqinlashishlar va shunday deb belgilangan. ML-model uslubiy jihatdan to‘g‘ri
qurilgan, lekin uning belgilari dala ma’lumotlaridan emas, qoidalardan olingan. Shu sababli vosita namoyish,
o‘qitish va variantlarni solishtirish uchun yaroqli. Amaliy xavfsizlik qarorlari uchun **yaroqli emas**.

### B1. To‘g‘ri va tekshirilgan qismlar

| Soha | Usul | Dalil |
|---|---|---|
| Koordinatalar | Planetotsentrik kenglik va sharqiy uzunlik, USGS Jezero mahsulotlaridagidek; planetografik kenglik ma’lumot uchun ko‘rsatiladi | centric→graphic siljishining unit testi (Jezero da 0,204°) |
| Masofalar | Marsning o‘rtacha sferasida gaversinus, R = 3389,5 km; har bir qirraning 3D uzunligi √(dh² + dz²) | Ellipsoidga nisbatan xato bir necha km da 0,3 % dan kam, bu 50 m to‘r oldida ahamiyatsiz; eksport qilingan marshrut geometriyasi bilan tekshirilgan |
| Qiyalik | Kataklarning haqiqiy o‘lchamlari bo‘yicha gradiyentlar, dx = R·cos φ·Δλ | Analitik sirtlardagi testlar |
| Marshrut | Joiz evristikali A* (narx koeffitsienti ≥ 1), shuning uchun natija Deykstra optimumiga teng; to‘silgan kataklar orqali burchak kesilmaydi | Unit testlar |
| Mars vaqti | Mars24 algoritmi; TT − UTC astropy kabisa soniyalar jadvalidan | Allison & McEwen (2000) bilan mos keladi, Ls = 277,18759°; astropy 1999 yildan oldingi sanalarni ham to‘g‘rilaydi |
| Radio | Erkin fazodagi yo‘qotish, Eb/N0 va aloqa zaxirasi; egrilikni hisobga olgan holda relyef ustidagi to‘g‘ri ko‘rinish | Masofa ikki baravar oshsa +6,02 dB (test) |
| Orbitalar | Ikki jism masalasi, aylana orbitalar, davr 2π√(a³/GM) | Standart |
| Navigatsiya | Kengaytirilgan Kalman filtri (x, y, ψ), 2σ moslik tekshiruvi bilan | Monte-Karlo statistikasi |
| GIS | IAU_2015:49900 dagi GeoPackage (WGS84 emas, Mars datumi) | Testlarda GeoPandas bilan qayta o‘qilgan |

### B2. Qabul qilingan soddalashtirishlar (ilovada belgilangan)
- **Inson Marsda yurishi.** Minetti metabolik sarfi va Tobler tezligi Yerda, skafandrsiz o‘lchangan. Ular
  g_Mars / g_Earth ga va 1,6 skafandr koeffitsientiga (faraz) moslashtirilgan. 0,38 g da skafandrda haqiqiy
  harakat chiziqli o‘zgarmaydi. Shuning uchun kislorod raqamlari taxminiy, taxminan ±30 %.
- **Radiatsiya.** RAD bazaviy dozasi 0,64 mZv/sutka atmosfera qalinligi bo‘yicha faraz qilingan daraja
  ko‘rsatkichi bilan masshtablanadi. Quyosh proton hodisalari son jihatdan modellanmaydi. Ular faqat DONKI
  belgisi orqali hisobga olinadi, bu esa evristika: DONKI Yerga yo‘naltirilgan, va faqat Marsni nomlagan ENLIL
  ta’sirlari hisobga olinadi.
- **Rover energiyasi.** Dumalash qarshiligi va qiyalikdagi tortish kuchi standart, lekin parametrlar namunaviy.
  Tungi va issiqlik yuklamalari soddalashtirilgan.
- **Relay.** Uchta orbital apparat sintetik. Mavjudlik raqamlari usul qanday ishlashini ko‘rsatadi; bu MRO,
  Odyssey yoki TGO uchun prognoz emas.
- **Xavflar.** Relyef ko‘rsatkichlari bo‘yicha chegaralar, qisman sahna persentillariga nisbatan. Bu
  tekshirilgan klassifikator emas.
- **Xavf matritsasi.** 1–5 tartib shkalalarida ehtimollik × ta’sir. Ko‘paytma xavflarni tartiblaydi, bu
  ehtimollik emas.
- **Yakuniy baho.** Vaznli min–max normallash. Tavsiya vaznlarga bog‘liq, shuning uchun vaznlarni foydalanuvchi
  o‘zgartira oladi va ular izohda ko‘rsatiladi.

### B3. Mashinali o‘qitish modeli: raqamlari nimani bildiradi

**To‘g‘ri bajarilgan qismlar:**
- model katakning o‘z qiyaligi va g‘adir-budurligini ko‘rmaydi;
- o‘qitish, validatsiya va test to‘plamlari bir-biriga kesishmaydigan fazoviy bloklar, shuning uchun
  avtokorrelyatsiyali qo‘shnilar orqali ma’lumot sizib o‘tmaydi;
- model va qaror chegarasi validatsiyada tanlanadi, test to‘plami bir marta ishlatiladi;
- ko‘rsatkichlar sinf ulushi bazasi bilan solishtiriladi;
- uchta model oilasi solishtiriladi;
- permutatsion ahamiyat model nimaga tayanishini ko‘rsatadi.

**Cheklov:**
- **Belgilar DEM bo‘yicha aniq qoidalardan olingan** (qiyalik > 15° yoki g‘adir-budurlik > 2 m), inson
  belgilashi yoki dala natijalaridan emas. Shuning uchun model shu qoidalarni atrof bo‘yicha bashorat qilishni
  o‘rganadi. Uning test bahosi yangi xarita bloklariga qanchalik yaxshi umumlashishini o‘lchaydi, haqiqiy
  astronavt u yerdan o‘ta olishini emas.
- SINTETIK DEM da baholar juda yuqori (F1 ≈ 0,97), chunki protsedurali relyef silliq. Bu ilovada yozilgan, va
  haqiqiy relyefda raqamlar pastroq bo‘ladi.

**Modelni ilmiy jihatdan kuchli qilish uchun:**
1. Haqiqiy CTX DEM da qayta o‘qitish (07-modulda bir bosish).
2. Odamlar belgilagan relyef sinflaridan foydalanish, masalan NASA-JPL ning ko‘pchilik tomonidan belgilangan
   AI4Mars rover tasvirlari to‘plami yoki HiRISE asosidagi o‘tish imkoniyati xaritalari.
3. Perseverance haqiqiy yurishlari natijalari bilan tekshirish, masalan sirpanish va haqiqiy yo‘llar, ular iz
   moduli orqali mavjud.

### B4. Aniqlik (piksel o‘lchami) chegaralari
50 m tahlil to‘ri, hatto 20 m CTX DEM ham xarsang toshlar, kichik jarliklar va qum to‘lqinlarini ko‘rmaydi,
ya’ni piyodani aynan to‘xtatadigan to‘siqlarni. Haqiqiy chiqish rejasi uchun HiRISE DEM (taxminan 1 m) va
orbitadan toshlarni sanash kerak. Ilova arxitekturasi istalgan GeoTIFF DEM ni qabul qiladi, lekin bunday aniqlik
bu yerda sinovdan o‘tkazilmagan.

### B5. Bu versiyada tekshirilmagan narsalar
- haqiqiy NASA yuklab olishlari, chunki serverlar yig‘ish kompyuteridan ochilmadi;
- haqiqiy yadrolar bilan SPICE;
- YOLO ni o‘qitish;
- haqiqiy Windows kompyuterida `.bat` skriptlar (ularning Linux muqobillari ishga tushirilgan).

Bu cheklovlar `LIMITATIONS.md` va `TEST_REPORT.md` da ham sanab o‘tilgan.
