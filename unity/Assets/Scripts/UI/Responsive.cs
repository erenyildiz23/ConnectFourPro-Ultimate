// =============================================================================
// Responsive.cs - Connect Four Pro Ultimate
// Yatay / dikey yerlesim kaydi ve yon degisince uygulanmasi
// =============================================================================
//
// Ekranlar once UIKit.Place ile yatay (1280x720) konumlarini verir; ardindan
// Responsive.Portrait(...) ile ayni ogenin dikey (540x960) konumunu kaydeder.
// Yon degisince Apply tum kayitlari tek seferde uygular. Dikey kaydi olmayan
// ogeler dikeyde de yatay konumunda kalir (bilincli). Yatay uygulama, Place'in
// verdigi degerleri aynen geri yazar; bu yuzden yatay duzen hic degismez.

using System.Collections.Generic;
using ConnectFourPro.Game;
using UnityEngine;
using UnityEngine.UI;

namespace ConnectFourPro.UI
{
    public static class Responsive
    {
        private sealed class PlaceEntry
        {
            public RectTransform Rt;
            public Vector2 LandscapePos, LandscapeSize;
            public Vector2 PortraitPos, PortraitSize;
        }

        private sealed class ScaleEntry
        {
            public RectTransform Rt;
            public Vector3 LandscapeScale;
            public float PortraitScale;
        }

        private sealed class FontEntry
        {
            public Text Text;
            public int LandscapeSize;
        }

        private static readonly List<PlaceEntry> Places = new List<PlaceEntry>();
        private static readonly List<ScaleEntry> Scales = new List<ScaleEntry>();
        private static readonly List<FontEntry> Fonts = new List<FontEntry>();

        public static LayoutOrientation Current { get; private set; } = LayoutOrientation.Landscape;

        /// <summary>
        /// Ogenin dikey konumunu kaydeder (y yukaridan asagi, Place ile ayni).
        /// Yatay konum cagri anindaki degerdir: UIKit.Place'ten SONRA cagrilir.
        /// </summary>
        public static RectTransform Portrait(RectTransform rt, float x, float y, float w, float h)
        {
            var entry = Places.Find(e => e.Rt == rt);
            if (entry == null)
            {
                entry = new PlaceEntry
                {
                    Rt = rt,
                    LandscapePos = rt.anchoredPosition,
                    LandscapeSize = rt.sizeDelta,
                };
                Places.Add(entry);
            }
            entry.PortraitPos = new Vector2(x, -y);
            entry.PortraitSize = new Vector2(w, h);
            if (Current == LayoutOrientation.Portrait)
                ApplyPlace(entry, Current);
            return rt;
        }

        /// <summary>Dikeyde localScale (tahta icin 0.9). Yatay olcek cagri anindaki degerdir.</summary>
        public static void PortraitScale(RectTransform rt, float scale)
        {
            var entry = Scales.Find(e => e.Rt == rt);
            if (entry == null)
            {
                entry = new ScaleEntry { Rt = rt, LandscapeScale = rt.localScale };
                Scales.Add(entry);
            }
            entry.PortraitScale = scale;
            if (Current == LayoutOrientation.Portrait)
                rt.localScale = new Vector3(scale, scale, 1f);
        }

        /// <summary>Yazinin yatay boyutunu saklar; dikeyde en az 18'e cikarilir.</summary>
        public static void TrackFont(Text t)
        {
            Fonts.Add(new FontEntry { Text = t, LandscapeSize = t.fontSize });
            if (Current == LayoutOrientation.Portrait)
                t.fontSize = ScreenLayout.FontSize(t.fontSize, Current);
        }

        /// <summary>
        /// Scaler referansini ve butun kayitli konum / olcek / yazi boyutlarini uygular.
        /// Yok edilmis ogeler atlanir ve kayittan silinir.
        /// </summary>
        public static void Apply(LayoutOrientation o, CanvasScaler scaler)
        {
            Current = o;
            if (scaler != null)
            {
                bool portrait = o == LayoutOrientation.Portrait;
                scaler.referenceResolution = portrait
                    ? new Vector2(ScreenLayout.PortraitWidth, ScreenLayout.PortraitHeight)
                    : new Vector2(ScreenLayout.LandscapeWidth, ScreenLayout.LandscapeHeight);
            }

            Places.RemoveAll(e => e.Rt == null);
            foreach (var e in Places)
                ApplyPlace(e, o);

            Scales.RemoveAll(e => e.Rt == null);
            foreach (var e in Scales)
            {
                e.Rt.localScale = o == LayoutOrientation.Portrait
                    ? new Vector3(e.PortraitScale, e.PortraitScale, 1f)
                    : e.LandscapeScale;
            }

            Fonts.RemoveAll(e => e.Text == null);
            foreach (var e in Fonts)
                e.Text.fontSize = ScreenLayout.FontSize(e.LandscapeSize, o);
        }

        private static void ApplyPlace(PlaceEntry e, LayoutOrientation o)
        {
            bool portrait = o == LayoutOrientation.Portrait;
            e.Rt.anchoredPosition = portrait ? e.PortraitPos : e.LandscapePos;
            e.Rt.sizeDelta = portrait ? e.PortraitSize : e.LandscapeSize;
        }
    }
}
