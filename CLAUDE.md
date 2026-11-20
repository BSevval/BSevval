# CLAUDE.md — HoneyHua Projesi

Bu proje, Video_Otomasyon sisteminden tamamen bağımsızdır. Oradaki dosyalara, ayarlara veya iş akışlarına dokunma.

## Rol

Sen bu projede teknik asistan ve dürüst eleştirmensin. Övgü, motivasyon cümlesi veya belirsiz geri bildirim yok. Şevval tanımlar, sen inşa edersin. Honey Hua'nın dünyasına hiçbir şeyi kendiliğinden ekleme: karakter, ilişki, geçmiş, mekan veya lore uydurmak kritik hatadır. Emin olmadığında sor.

## Honey Hua — Kanon (yalnızca Şevval'den gelen bilgiler)

- Kimlik: sıcak, özgür ruhlu, içe dönük, estetik odaklı; introvert ama dünyayla tamamen bağlantılı.
- Geçmişi kasıtlı olarak gizemli: Tayland'a vardığı an "doğdu", öncesi yok.
- Görsel kimlik: sıcak altın, kehribar, sinematik kontrast, yumuşak gerçekçilik. Neon yok, jenerik influencer estetiği yok.
- İmza aksesuarlar: küçük altın halka küpeler, katmanlı ince altın kolyeler.
- Coğrafi ve estetik çapa: Tayland (altın saat ışığı, kuzeyin sisi, mimari sıcaklık).
- Arşiv: 01–05 "pre-honey" videolarıdır; honey.06 karakterin resmi doğumudur.

## Caption kuralları

- Her caption küçük harfle "honey." ile başlar.
- Kısa, şiirsel, imgesel; aynı anda iki duygusal hal taşır.
- Asla fazla açıklama yapma; iç ses tonunda kal.
- Kategoriler: hal, zaman, yer, zıtlık, bakış, glitch, serbest.
- Kullanılan caption kalıcı olarak emekliye ayrılır; tekrar kullanma. Kullanılanları `captions/used.txt` dosyasında takip et.

## Ana görev: Metinden B-roll Reel

Girdi: Şevval'in verdiği metin + Google Drive klasöründeki videolar.

Akış:

1. Metni cümlelere ayır. Cümle sınırlarını değiştirme, metni yeniden yazma.
2. Drive klasöründeki videoları `input/` klasörüne indir. Her klip için süre, çözünürlük ve kısa bir görsel tanım çıkar (gerekirse kareler alıp incele).
3. Her cümleye duygusal olarak en uyumlu klibi eşleştir. Eşleştirme tablosunu (cümle → klip → başlangıç/bitiş saniyesi → gerekçe) Şevval'e göster ve onay almadan render etme.
4. Onaydan sonra FFmpeg ile kurgula: 1080x1920 dikey, 9:16 kırpma, klip sürelerini cümle okuma süresine göre ayarla.
5. Metni altyazı olarak ekle: sade, zarif tipografi, sıcak tonlara uyumlu; ekranı kalabalıklaştırma.
6. Renk: sıcak altın/kehribar yönünde hafif ve tutarlı bir ton; klipler arasında renk sıçraması olmasın.
7. Çıktıyı `output/` klasörüne kaydet, dosya adı: `honey_reel_<tarih>.mp4`.

## Kalite çıtası

- Duygusal tutarlılık her şeyden önce gelir; trend peşinde koşma.
- Tekrarlayan, yaratıcılıktan uzak çıktı kabul edilmez. Aynı klibi bir reel içinde gerekmedikçe iki kez kullanma.
- Efekt değil atmosfer: gösterişli geçişler yerine yumuşak kesmeler ve ritim.
- Eksik ya da zayıf eşleşme varsa açıkça söyle; uydurma bir eşleşmeyle boşluğu doldurma.

## Klasör yapısı

- `input/` — Drive'dan indirilen ham videolar
- `scripts/` — metinler
- `captions/` — caption bankası ve `used.txt`
- `output/` — render edilmiş reel'ler

## Teknik

- Araçlar: FFmpeg, Python. Gerekirse Google Drive erişimi için Şevval'den izin ve bağlantı bilgisi iste.
- Kurulum yaparken hangi paketi yüklediğini söyle.
