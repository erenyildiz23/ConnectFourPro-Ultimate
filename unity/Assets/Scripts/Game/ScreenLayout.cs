// Ekran yonu secimi ve yerlesim sabitleri. Saf C#: UnityEngine kullanmaz, testlenebilir.
namespace ConnectFourPro.Game
{
    public enum LayoutOrientation { Landscape, Portrait }

    public static class ScreenLayout
    {
        // Canvas referans cozunurlukleri.
        public const float LandscapeWidth = 1280f;
        public const float LandscapeHeight = 720f;
        public const float PortraitWidth = 540f;
        public const float PortraitHeight = 960f;

        // Portrede tahta, kullanilabilir genisligin bu kadari kadar olur.
        public const float PortraitBoardScale = 0.9f;

        // Portrede okunabilirlik icin en kucuk yazi boyutu.
        public const int PortraitMinFontSize = 18;

        // Yukseklik genislikten buyukse portre; esitlik ve gecersiz (0x0) boyut yatay sayilir.
        public static LayoutOrientation For(int width, int height)
            => height > width ? LayoutOrientation.Portrait : LayoutOrientation.Landscape;

        public static int FontSize(int landscapeSize, LayoutOrientation o)
            => o == LayoutOrientation.Portrait && landscapeSize < PortraitMinFontSize
                ? PortraitMinFontSize
                : landscapeSize;
    }
}
