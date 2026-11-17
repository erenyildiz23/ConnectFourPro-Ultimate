// Oyun sunucusunun adresi (REST + Socket.IO).
// Bos ("") = oyunu sunan sayfanin adresi: oyun Flask sunucusunun /play/ rotasindan
// sunuluyorsa dogru deger budur. Oyun baska bir siteden (ornegin itch.io) sunulacaksa
// scripts/make_itch_zip.py bu dosyayi https://SUNUCU (sonda / yok) ile yeniden yazar;
// sunucuda CORS_ALLOWED_ORIGINS da ayarlanmalidir (docs/KURULUM.md -> 14).
window.CF4_SERVER_URL = "";
