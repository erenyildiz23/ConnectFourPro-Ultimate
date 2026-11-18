// =============================================================================
// QuickChat.cs - Connect Four Pro Ultimate
// Hazir sohbet mesajlari (sunucu yalnizca numara tasir: chat_quick / chat_message)
// =============================================================================
//
// Numara (0-7) dizideki sirayi gosterir; sira sunucu ve diger istemcilerle ayni
// kalmalidir. Metinler Turkce tutulur, ekranda Loc.T ile alicinin diline cevrilir.

namespace ConnectFourPro.Game
{
    public static class QuickChat
    {
        public static readonly string[] Messages =
        {
            "İyi oyun!",
            "Bol şans!",
            "Güzel hamle!",
            "Hay aksi!",
            "Düşünüyorum...",
            "Teşekkürler!",
            "Rövanş?",
            "Selam!",
        };

        /// <summary>Gecerli mesaj numarasi mi (0..Messages.Length-1).</summary>
        public static bool IsValid(int msgId) => msgId >= 0 && msgId < Messages.Length;
    }
}
