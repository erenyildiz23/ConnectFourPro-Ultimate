// =============================================================================
// BoardView.cs - Connect Four Pro Ultimate
// Tahta gorunumu: hucreler, taslar, dusme animasyonu, kazanan dortlu vurgusu
// =============================================================================

using System;
using ConnectFourPro.Core;
using UnityEngine;
using UnityEngine.UI;

namespace ConnectFourPro.UI
{
    public sealed class BoardView : MonoBehaviour
    {
        public const float Cell = 80f;
        private const float Width = Cell * Board.Cols;
        private const float Height = Cell * Board.Rows;
        private const float Gravity = 5200f;         // px/s^2
        private const float StartSpeed = 300f;       // px/s

        private readonly Image[,] _pieces = new Image[Board.Cols, Board.Rows];
        private readonly Image[,] _glows = new Image[Board.Cols, Board.Rows];
        private Image _hover;
        private Image _falling;
        private RectTransform _area;

        // Animasyon durumu
        private float _fallY;
        private float _fallTargetY;
        private float _fallSpeed;
        private Action _onLanded;

        private Func<GameState> _game;
        private Func<bool> _canMove;
        private Func<int> _hoverPiece;
        private int _hoverCol = -1;

        /// <summary>Oyuncu bir sutuna tikladi.</summary>
        public event Action<int> ColumnClicked;

        public bool IsAnimating => _onLanded != null || (_falling != null && _falling.enabled);

        public static BoardView Create(Transform parent, float x, float y,
                                       Func<GameState> game, Func<bool> canMove, Func<int> hoverPiece)
        {
            var root = UIKit.Rect(parent, "Board");
            UIKit.Place(root, x, y, Width, Height);
            var view = root.gameObject.AddComponent<BoardView>();
            view._game = game;
            view._canMove = canMove;
            view._hoverPiece = hoverPiece;
            view.Build(root);
            return view;
        }

        private static Vector2 CellCenter(int col, int row) =>
            new Vector2(-Width / 2 + col * Cell + Cell / 2, -Height / 2 + row * Cell + Cell / 2);

        private float TopY => Height / 2 + Cell * 0.6f;

        private void Build(RectTransform root)
        {
            _area = root;
            var frame = UIKit.Panel(root, "Frame", Theme.Board);
            frame.rectTransform.anchorMin = Vector2.zero;
            frame.rectTransform.anchorMax = Vector2.one;
            frame.rectTransform.offsetMin = new Vector2(-12, -12);
            frame.rectTransform.offsetMax = new Vector2(12, 12);

            // Hover gostergesi (tahtanin ustunde)
            _hover = MakeDisc(root, "Hover", Theme.Hover, Cell - 20);
            _hover.enabled = false;

            for (int c = 0; c < Board.Cols; c++)
                for (int r = 0; r < Board.Rows; r++)
                {
                    var glow = MakeDisc(root, $"Glow {c},{r}", Theme.WinHighlight, Cell);
                    glow.rectTransform.anchoredPosition = CellCenter(c, r);
                    glow.enabled = false;
                    _glows[c, r] = glow;

                    var hole = MakeDisc(root, $"Cell {c},{r}", Theme.CellBackground, Cell - 10);
                    hole.rectTransform.anchoredPosition = CellCenter(c, r);

                    var piece = MakeDisc(root, $"Piece {c},{r}", Theme.Red, Cell - 16);
                    piece.rectTransform.anchoredPosition = CellCenter(c, r);
                    piece.enabled = false;
                    _pieces[c, r] = piece;
                }

            _falling = MakeDisc(root, "Falling", Theme.Red, Cell - 16);
            _falling.enabled = false;

            // Sutun tiklama alanlari (en ustte, saydam)
            for (int c = 0; c < Board.Cols; c++)
            {
                int col = c;
                var hit = UIKit.Image(root, "Column " + c, new Color(0, 0, 0, 0));
                var rt = hit.rectTransform;
                rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
                rt.sizeDelta = new Vector2(Cell, Height + Cell);
                rt.anchoredPosition = new Vector2(CellCenter(c, 0).x, Cell / 2);
                var relay = UIKit.Relay(hit.gameObject);
                relay.Enter = () => _hoverCol = col;
                relay.Exit = () =>
                {
                    if (_hoverCol == col)
                        _hoverCol = -1;
                };
                relay.Click = () => ColumnClicked?.Invoke(col);
            }
        }

        private static Image MakeDisc(Transform parent, string name, Color color, float size)
        {
            var img = UIKit.Image(parent, name, color, UIKit.Circle);
            img.raycastTarget = false;
            var rt = img.rectTransform;
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(size, size);
            return img;
        }

        /// <summary>Tasi sutunun ustunden satirina dusurur; bitince onLanded cagrilir.</summary>
        public void AnimateDrop(int col, int row, int piece, Action onLanded)
        {
            FinishAnimation();
            _falling.color = Theme.PieceColor(piece);
            _falling.enabled = true;
            _fallY = TopY;
            _fallTargetY = CellCenter(col, row).y;
            _fallSpeed = StartSpeed;
            _falling.rectTransform.anchoredPosition = new Vector2(CellCenter(col, 0).x, _fallY);
            _onLanded = onLanded;
        }

        /// <summary>Suren animasyonu aninda bitirir (geri cagrisi calisir).</summary>
        public void FinishAnimation()
        {
            if (_onLanded == null)
            {
                _falling.enabled = false;
                return;
            }
            var callback = _onLanded;
            _onLanded = null;
            _falling.enabled = false;
            callback();
        }

        /// <summary>Animasyonu geri cagrisini calistirmadan iptal eder.</summary>
        public void CancelAnimation()
        {
            _onLanded = null;
            _falling.enabled = false;
        }

        private void Update()
        {
            if (_onLanded != null)
            {
                _fallSpeed += Gravity * Time.unscaledDeltaTime;
                _fallY -= _fallSpeed * Time.unscaledDeltaTime;
                if (_fallY <= _fallTargetY)
                {
                    _fallY = _fallTargetY;
                    FinishAnimation();
                }
                else
                {
                    var p = _falling.rectTransform.anchoredPosition;
                    _falling.rectTransform.anchoredPosition = new Vector2(p.x, _fallY);
                }
            }
            Refresh();
        }

        private void Refresh()
        {
            var game = _game?.Invoke();
            if (game == null)
                return;

            ulong winMask = game.Status == GameStatus.Win ? game.WinningMask : 0;
            float pulse = Mathf.Abs(Time.unscaledTime * 3f % 2f - 1f);
            for (int c = 0; c < Board.Cols; c++)
                for (int r = 0; r < Board.Rows; r++)
                {
                    int cell = game.GetCell(c, r);
                    var piece = _pieces[c, r];
                    piece.enabled = cell != Board.Empty;
                    if (piece.enabled)
                        piece.color = Theme.PieceColor(cell);

                    bool winning = ((winMask >> Board.BitIndex(c, r)) & 1) != 0;
                    var glow = _glows[c, r];
                    glow.enabled = winning;
                    if (winning)
                    {
                        float size = Cell + pulse * 12f;
                        glow.rectTransform.sizeDelta = new Vector2(size, size);
                    }
                }

            bool showHover = _hoverCol >= 0 && !IsAnimating && _canMove != null && _canMove();
            _hover.enabled = showHover;
            if (showHover)
            {
                var color = Theme.PieceColor(_hoverPiece?.Invoke() ?? Board.Player1);
                color.a = 0.75f;
                _hover.color = color;
                _hover.rectTransform.anchoredPosition = new Vector2(CellCenter(_hoverCol, 0).x, TopY);
            }
        }

        public RectTransform Area => _area;
    }
}
