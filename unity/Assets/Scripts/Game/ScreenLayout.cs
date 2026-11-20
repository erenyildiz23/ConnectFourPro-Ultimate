// Ekran yonu secimi ve yerlesim sabitleri. Saf C#: UnityEngine kullanmaz, testlenebilir.
namespace ConnectFourPro.Game
{
    public enum LayoutOrientation { Landscape, Portrait }

    /// <summary>
    /// Alt alta esit aralikli satirlar (dugme / liste satiri). y degerleri UIKit.Place gibi
    /// ekranin ustunden asagi dogru ve satirin merkezidir.
    /// </summary>
    public readonly struct RowLayout
    {
        public readonly float First;
        public readonly float Step;
        public readonly float Height;
        public readonly int Count;

        public RowLayout(float first, float step, float height, int count)
        {
            First = first;
            Step = step;
            Height = height;
            Count = count;
        }

        public float Center(int index) => First + Step * index;

        /// <summary>Ilk satirin ust kenari.</summary>
        public float Top => First - Height / 2f;

        /// <summary>Son satirin alt kenari.</summary>
        public float Bottom => Count <= 0 ? Top : Center(Count - 1) + Height / 2f;
    }

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

        // Durum cubugunun ust kenari (GameBootstrap: yatay 52, dikey 72 px yuksek)
        public const float LandscapeContentBottom = LandscapeHeight - 52f;
        public const float PortraitContentBottom = PortraitHeight - 72f;

        public static float ContentBottom(LayoutOrientation o)
            => o == LayoutOrientation.Portrait ? PortraitContentBottom : LandscapeContentBottom;

        /// <summary>Son satir durum cubugunun ustunde biter mi?</summary>
        public static bool Fits(RowLayout rows, LayoutOrientation o) => rows.Bottom <= ContentBottom(o);

        /// <summary>
        /// Menu dugmeleri. WebGL'de 7 dugme: yatay (200 + 66 i), dikey (340 + 78 i); tests/e2e
        /// bu koordinatlara tiklar. Masaustundeki 8. dugme ("Oyunu Kapat") icin aralik daralir.
        /// </summary>
        public static RowLayout Menu(int items, LayoutOrientation o)
            => o == LayoutOrientation.Portrait
                ? new RowLayout(340f, items > 7 ? 70f : 78f, 60f, items)
                : new RowLayout(200f, items > 7 ? 58f : 66f, 52f, items);

        /// <summary>Turnuvalar listesi: yatayda tek satir, dikeyde iki yazi satiri + dugme.</summary>
        public static RowLayout TournamentList(LayoutOrientation o)
            => o == LayoutOrientation.Portrait
                ? new RowLayout(300f, 68f, 60f, 8)
                : new RowLayout(170f, 56f, 50f, 8);

        /// <summary>Turnuva sayfasindaki puan durumu basligi (satirlarin hemen ustu).</summary>
        public static float StandingsHeaderY(LayoutOrientation o)
            => o == LayoutOrientation.Portrait ? 362f : 205f;

        /// <summary>Turnuva sayfasindaki puan durumu satirlari.</summary>
        public static RowLayout Standings(LayoutOrientation o)
            => o == LayoutOrientation.Portrait
                ? new RowLayout(405f, 50f, 46f, 9)
                : new RowLayout(245f, 44f, 40f, 9);

        // Yukseklik genislikten buyukse portre; esitlik ve gecersiz (0x0) boyut yatay sayilir.
        public static LayoutOrientation For(int width, int height)
            => height > width ? LayoutOrientation.Portrait : LayoutOrientation.Landscape;

        public static int FontSize(int landscapeSize, LayoutOrientation o)
            => o == LayoutOrientation.Portrait && landscapeSize < PortraitMinFontSize
                ? PortraitMinFontSize
                : landscapeSize;
    }
}
