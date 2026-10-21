// =============================================================================
// UIKit.cs - Connect Four Pro Ultimate
// uGUI ogelerini koddan kuran yardimcilar ve renk paleti
// =============================================================================
//
// Arayuz sahneye elle yerlestirilmez; GameBootstrap calisinca bu sinifla kurulur.
// Boylece sahne dosyasi tek bir nesneden ibarettir, Git'te cakisma uretmez ve
// Unity'siz ortamda da gozden gecirilebilir. Yerlesim 1280x720 referans
// cozunurlugunde piksel cinsindendir; CanvasScaler ekrana gore olcekler.
//
// Yazi tipi: Unity'nin yerlesik LegacyRuntime.ttf'i (Liberation Sans). Turkce
// karakterleri (ç ğ ı İ ö ş ü) icerir ve ek kurulum gerektirmez.

using System;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace ConnectFourPro.UI
{
    public static class Theme
    {
        // src/gui_app.py COLORS ile ayni palet
        public static readonly Color Background = Rgb(26, 26, 46);
        public static readonly Color Board = Rgb(15, 52, 96);
        public static readonly Color Panel = Rgb(22, 33, 62);
        public static readonly Color Red = Rgb(233, 69, 96);
        public static readonly Color Yellow = Rgb(241, 196, 15);
        public static readonly Color White = Rgb(234, 234, 234);
        public static readonly Color Gray = Rgb(127, 140, 141);
        public static readonly Color Green = Rgb(46, 204, 113);
        public static readonly Color CellBackground = Rgb(10, 10, 21);
        public static readonly Color Hover = Rgb(52, 152, 219);
        public static readonly Color Button = Rgb(233, 69, 96);
        public static readonly Color Waiting = Rgb(230, 126, 34);
        public static readonly Color Playing = Rgb(46, 204, 113);
        public static readonly Color InputBackground = Rgb(44, 62, 80);
        public static readonly Color WinHighlight = Rgb(0, 255, 128);

        public const float ReferenceWidth = 1280f;
        public const float ReferenceHeight = 720f;

        public static Color Rgb(int r, int g, int b) => new Color(r / 255f, g / 255f, b / 255f);

        public static Color PieceColor(int piece) => piece == 1 ? Red : Yellow;
    }

    public static class UIKit
    {
        private static Font _font;
        private static Sprite _circle;
        private static Sprite _rounded;

        public static Font Font
        {
            get
            {
                if (_font == null)
                {
                    _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
                    if (_font == null)
                        _font = Resources.GetBuiltinResource<Font>("Arial.ttf");
                }
                return _font;
            }
        }

        /// <summary>Kenarlari yumusatilmis daire (tahta hucreleri ve taslar).</summary>
        public static Sprite Circle => _circle != null ? _circle : (_circle = MakeCircle(128));

        /// <summary>9-dilimli yuvarlak koseli dikdortgen (butonlar, paneller).</summary>
        public static Sprite Rounded => _rounded != null ? _rounded : (_rounded = MakeRounded(64, 16));

        private static Sprite MakeCircle(int size)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            float r = size / 2f;
            var pixels = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Mathf.Sqrt((x + 0.5f - r) * (x + 0.5f - r) + (y + 0.5f - r) * (y + 0.5f - r));
                    byte a = (byte)(Mathf.Clamp01(r - d) * 255);
                    pixels[y * size + x] = new Color32(255, 255, 255, a);
                }
            tex.SetPixels32(pixels);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        private static Sprite MakeRounded(int size, int radius)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            var pixels = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float cx = Mathf.Clamp(x + 0.5f, radius, size - radius);
                    float cy = Mathf.Clamp(y + 0.5f, radius, size - radius);
                    float d = Mathf.Sqrt((x + 0.5f - cx) * (x + 0.5f - cx) + (y + 0.5f - cy) * (y + 0.5f - cy));
                    byte a = (byte)(Mathf.Clamp01(radius - d) * 255);
                    pixels[y * size + x] = new Color32(255, 255, 255, a);
                }
            tex.SetPixels32(pixels);
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0,
                                 SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
        }

        // ------------------------------------------------------------------
        // Temel nesneler
        // ------------------------------------------------------------------

        public static Canvas CreateCanvas(Transform parent)
        {
            var go = new GameObject("Canvas", typeof(RectTransform));
            go.transform.SetParent(parent, false);
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = go.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(Theme.ReferenceWidth, Theme.ReferenceHeight);
            scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
            scaler.matchWidthOrHeight = 0.5f;
            go.AddComponent<GraphicRaycaster>();
            return canvas;
        }

        public static void EnsureEventSystem(Transform parent)
        {
            if (UnityEngine.Object.FindAnyObjectByType<EventSystem>() != null)
                return;
            var go = new GameObject("EventSystem");
            go.transform.SetParent(parent, false);
            go.AddComponent<EventSystem>();
#if CF4_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            go.AddComponent<UnityEngine.InputSystem.UI.InputSystemUIInputModule>();
#else
            go.AddComponent<StandaloneInputModule>();
#endif
        }

        /// <summary>Ebeveyni tamamen kaplayan bos alan.</summary>
        public static RectTransform Stretch(Transform parent, string name)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            var rt = (RectTransform)go.transform;
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            return rt;
        }

        /// <summary>
        /// Ust-orta noktaya gore yerlesim: (x, y) ogenin merkezinin ekranin ust ortasina
        /// gore konumu (y asagi dogru artar, Python/pygame koordinatlarina benzer).
        /// </summary>
        public static RectTransform Place(RectTransform rt, float x, float y, float w, float h)
        {
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 1f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(x, -y);
            return rt;
        }

        public static RectTransform Rect(Transform parent, string name)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return (RectTransform)go.transform;
        }

        public static Image Image(Transform parent, string name, Color color, Sprite sprite = null)
        {
            var rt = Rect(parent, name);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = color;
            if (sprite != null)
            {
                img.sprite = sprite;
                img.type = sprite == Rounded ? UnityEngine.UI.Image.Type.Sliced : UnityEngine.UI.Image.Type.Simple;
            }
            return img;
        }

        public static Image Panel(Transform parent, string name, Color color) => Image(parent, name, color, Rounded);

        public static Text Text(Transform parent, string text, int size, Color color,
                                TextAnchor align = TextAnchor.MiddleCenter, FontStyle style = FontStyle.Normal)
        {
            var rt = Rect(parent, "Text");
            var t = rt.gameObject.AddComponent<Text>();
            t.font = Font;
            t.text = text;
            t.fontSize = size;
            t.fontStyle = style;
            t.color = color;
            t.alignment = align;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            t.raycastTarget = false;
            return t;
        }

        /// <summary>Ust-ortaya gore yerlestirilmis yazi.</summary>
        public static Text Label(Transform parent, string text, int size, Color color, float x, float y,
                                 float w = 900, float h = 40, TextAnchor align = TextAnchor.MiddleCenter,
                                 FontStyle style = FontStyle.Normal)
        {
            var t = Text(parent, text, size, color, align, style);
            Place(t.rectTransform, x, y, w, h);
            return t;
        }

        public static Button Button(Transform parent, string label, Color color, UnityAction onClick,
                                    float x, float y, float w, float h, int fontSize = 20)
        {
            var img = Image(parent, "Button " + label, color, Rounded);
            Place(img.rectTransform, x, y, w, h);
            var button = img.gameObject.AddComponent<Button>();
            var colors = button.colors;
            colors.highlightedColor = new Color(1.15f, 1.15f, 1.15f, 1f);
            colors.pressedColor = new Color(0.85f, 0.85f, 0.85f, 1f);
            colors.disabledColor = new Color(0.6f, 0.6f, 0.6f, 0.6f);
            colors.colorMultiplier = 1f;
            button.colors = colors;
            if (onClick != null)
                button.onClick.AddListener(onClick);
            var text = Text(img.transform, label, fontSize, Theme.White);
            var trt = text.rectTransform;
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = trt.offsetMax = Vector2.zero;
            return button;
        }

        public static void SetLabel(Button button, string label) =>
            button.GetComponentInChildren<Text>().text = label;

        public static InputField Input(Transform parent, string placeholder, bool password,
                                       float x, float y, float w, float h, int characterLimit)
        {
            var bg = Image(parent, "Input " + placeholder, Theme.InputBackground, Rounded);
            Place(bg.rectTransform, x, y, w, h);
            var field = bg.gameObject.AddComponent<InputField>();
            var colors = field.colors;
            colors.highlightedColor = new Color(1.1f, 1.1f, 1.1f, 1f);
            colors.selectedColor = new Color(1.2f, 1.25f, 1.35f, 1f);
            field.colors = colors;

            var text = Text(bg.transform, "", 22, Theme.White, TextAnchor.MiddleLeft);
            text.supportRichText = false;
            text.horizontalOverflow = HorizontalWrapMode.Overflow;
            Inset(text.rectTransform, 14);
            var ph = Text(bg.transform, placeholder, 20, Theme.Gray, TextAnchor.MiddleLeft, FontStyle.Italic);
            Inset(ph.rectTransform, 14);

            field.textComponent = text;
            field.placeholder = ph;
            field.characterLimit = characterLimit;
            field.lineType = UnityEngine.UI.InputField.LineType.SingleLine;
            if (password)
            {
                field.contentType = UnityEngine.UI.InputField.ContentType.Password;
                field.asteriskChar = '*';
            }
            return field;
        }

        private static void Inset(RectTransform rt, float padding)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(padding, 4);
            rt.offsetMax = new Vector2(-padding, -4);
        }

        /// <summary>Tiklama / imlec olaylarini bir geri cagriya baglar.</summary>
        public static PointerRelay Relay(GameObject go)
        {
            // ?? kullanilmaz: Unity nesnelerinin "sahte null" degeri ?? ile yakalanmaz
            var relay = go.GetComponent<PointerRelay>();
            return relay != null ? relay : go.AddComponent<PointerRelay>();
        }
    }

    /// <summary>uGUI isaretci olaylarini Action'lara ileten bilesen.</summary>
    public sealed class PointerRelay : MonoBehaviour, IPointerClickHandler, IPointerEnterHandler, IPointerExitHandler
    {
        public Action Click;
        public Action Enter;
        public Action Exit;

        public void OnPointerClick(PointerEventData eventData)
        {
            if (eventData.button == PointerEventData.InputButton.Left)
                Click?.Invoke();
        }

        public void OnPointerEnter(PointerEventData eventData) => Enter?.Invoke();
        public void OnPointerExit(PointerEventData eventData) => Exit?.Invoke();
    }
}
