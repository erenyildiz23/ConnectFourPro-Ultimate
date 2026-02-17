// =============================================================================
// BoardController.cs - Connect Four Pro
// Oyun tahtasi gorsel yonetimi ve animasyonlar
// =============================================================================

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using ConnectFourPro.Core;

namespace ConnectFourPro.Managers
{
    public class BoardController : MonoBehaviour
    {
        [Header("Prefabs")]
        public GameObject CellPrefab;
        public GameObject PiecePrefab;
        public GameObject HoverIndicatorPrefab;

        [Header("Board Settings")]
        public float CellSize = 1.0f;
        public float DropSpeed = 15f;
        public float BoardOffsetX = -3f;
        public float BoardOffsetY = -2.5f;

        [Header("Colors")]
        public Color BoardColor = new Color(15f/255f, 52f/255f, 96f/255f);
        public Color CellBgColor = new Color(10f/255f, 10f/255f, 21f/255f);
        public Color RedPieceColor = new Color(233f/255f, 69f/255f, 96f/255f);
        public Color YellowPieceColor = new Color(241f/255f, 196f/255f, 15f/255f);
        public Color HoverColor = new Color(52f/255f, 152f/255f, 219f/255f, 0.6f);
        public Color WinHighlightColor = new Color(0f, 1f, 128f/255f);

        // Dahili referanslar
        private GameObject[,] _cellObjects;
        private GameObject[,] _pieceObjects;
        private GameObject _hoverIndicator;
        private GameObject _boardBackground;
        private int _hoverCol = -1;

        // Animasyon durumu
        private bool _isAnimating;
        private GameObject _animatingPiece;
        private float _animTargetY;
        private int _animCol;
        private int _animRow;
        private Action _animCallback;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;
            CreateBoard();
            CreateHoverIndicator();

            if (_gm != null)
            {
                _gm.OnGameUpdated += RefreshBoard;
                _gm.OnGameOver += OnGameOver;
            }
        }

        private void Update()
        {
            HandleHover();
            UpdateAnimation();
        }

        // =========================================================================
        // TAHTA OLUSTURMA
        // =========================================================================

        private void CreateBoard()
        {
            _cellObjects = new GameObject[GameConstants.Cols, GameConstants.Rows];
            _pieceObjects = new GameObject[GameConstants.Cols, GameConstants.Rows];

            // Arka plan
            _boardBackground = GameObject.CreatePrimitive(PrimitiveType.Quad);
            _boardBackground.transform.SetParent(transform);
            _boardBackground.transform.localPosition = new Vector3(
                BoardOffsetX + (GameConstants.Cols * CellSize) / 2f - CellSize / 2f,
                BoardOffsetY + (GameConstants.Rows * CellSize) / 2f - CellSize / 2f,
                0.1f
            );
            _boardBackground.transform.localScale = new Vector3(
                GameConstants.Cols * CellSize + 0.4f,
                GameConstants.Rows * CellSize + 0.4f,
                1f
            );
            var bgRenderer = _boardBackground.GetComponent<Renderer>();
            bgRenderer.material = new Material(Shader.Find("Sprites/Default"));
            bgRenderer.material.color = BoardColor;

            // Hucreler
            for (int col = 0; col < GameConstants.Cols; col++)
            {
                for (int row = 0; row < GameConstants.Rows; row++)
                {
                    Vector3 pos = GetCellPosition(col, row);

                    // Hucre arka plani (daire)
                    GameObject cell;
                    if (CellPrefab != null)
                    {
                        cell = Instantiate(CellPrefab, pos, Quaternion.identity, transform);
                    }
                    else
                    {
                        cell = CreateCircle(CellSize * 0.85f, CellBgColor);
                        cell.transform.position = pos;
                        cell.transform.SetParent(transform);
                    }
                    cell.name = $"Cell_{col}_{row}";
                    _cellObjects[col, row] = cell;
                }
            }
        }

        private void CreateHoverIndicator()
        {
            if (HoverIndicatorPrefab != null)
            {
                _hoverIndicator = Instantiate(HoverIndicatorPrefab, Vector3.zero, Quaternion.identity, transform);
            }
            else
            {
                _hoverIndicator = CreateCircle(CellSize * 0.7f, HoverColor);
                _hoverIndicator.transform.SetParent(transform);
            }
            _hoverIndicator.SetActive(false);
        }

        // =========================================================================
        // HOVER YONETIMI
        // =========================================================================

        private void HandleHover()
        {
            if (_gm == null || _isAnimating) return;

            var state = _gm.AppState;
            if (state != GameAppState.PlayingAI && state != GameAppState.PlayingOnline)
            {
                _hoverIndicator?.SetActive(false);
                return;
            }

            // Mouse pozisyonundan sutun hesapla
            Vector3 mouseWorld = Camera.main.ScreenToWorldPoint(Input.mousePosition);
            mouseWorld.z = 0;

            int col = WorldToColumn(mouseWorld);

            bool canPlay = false;
            if (state == GameAppState.PlayingAI)
                canPlay = _gm.Game.CurrentPlayer == GameConstants.Player1Piece && !_gm.AIThinking;
            else if (state == GameAppState.PlayingOnline)
                canPlay = _gm.Game.CurrentPlayer == _gm.MyPiece;

            if (col >= 0 && col < GameConstants.Cols && canPlay && !_gm.Game.GameOver && !_gm.IsSpectator)
            {
                _hoverCol = col;
                _hoverIndicator.SetActive(true);
                _hoverIndicator.transform.position = new Vector3(
                    BoardOffsetX + col * CellSize,
                    BoardOffsetY + GameConstants.Rows * CellSize + 0.3f,
                    -0.2f
                );
            }
            else
            {
                _hoverCol = -1;
                _hoverIndicator?.SetActive(false);
            }

            // Tikla
            if (Input.GetMouseButtonDown(0) && _hoverCol >= 0)
            {
                _gm.HandleColumnClick(_hoverCol);
            }
        }

        // =========================================================================
        // ANIMASYON
        // =========================================================================

        public void AnimateDrop(int col, int row, int piece, Action callback)
        {
            _isAnimating = true;
            _gm.IsAnimating = true;
            _animCol = col;
            _animRow = row;
            _animCallback = callback;

            Color pieceColor = piece == GameConstants.Player1Piece ? RedPieceColor : YellowPieceColor;

            float startY = BoardOffsetY + GameConstants.Rows * CellSize + 1f;
            _animTargetY = BoardOffsetY + row * CellSize;

            if (PiecePrefab != null)
            {
                _animatingPiece = Instantiate(PiecePrefab, new Vector3(BoardOffsetX + col * CellSize, startY, -0.1f), Quaternion.identity, transform);
            }
            else
            {
                _animatingPiece = CreateCircle(CellSize * 0.8f, pieceColor);
                _animatingPiece.transform.position = new Vector3(BoardOffsetX + col * CellSize, startY, -0.1f);
                _animatingPiece.transform.SetParent(transform);
            }

            // Rengi ayarla
            var renderer = _animatingPiece.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = pieceColor;
            }
        }

        private void UpdateAnimation()
        {
            if (!_isAnimating || _animatingPiece == null) return;

            Vector3 pos = _animatingPiece.transform.position;
            pos.y -= DropSpeed * Time.deltaTime;

            if (pos.y <= _animTargetY)
            {
                pos.y = _animTargetY;
                _animatingPiece.transform.position = pos;

                // Animasyon tamamlandi - tasi kalici yap
                _isAnimating = false;
                _gm.IsAnimating = false;

                // Animasyon objesini kalici tas olarak kaydet
                if (_pieceObjects[_animCol, _animRow] != null)
                {
                    Destroy(_pieceObjects[_animCol, _animRow]);
                }
                _pieceObjects[_animCol, _animRow] = _animatingPiece;
                _animatingPiece = null;

                _animCallback?.Invoke();
                _animCallback = null;
            }
            else
            {
                _animatingPiece.transform.position = pos;
            }
        }

        // =========================================================================
        // TAHTA GUNCELLEME
        // =========================================================================

        public void RefreshBoard()
        {
            if (_gm == null || _gm.Game == null) return;

            var game = _gm.Game;

            for (int col = 0; col < GameConstants.Cols; col++)
            {
                for (int row = 0; row < GameConstants.Rows; row++)
                {
                    int cell = game.GetCell(col, row);
                    bool isWinning = game.GameOver && game.Winner.HasValue && game.IsWinningPosition(col, row);

                    if (cell != GameConstants.Empty)
                    {
                        // Zaten bir tas varsa guncelle, yoksa olustur
                        if (_pieceObjects[col, row] == null)
                        {
                            Color color = cell == GameConstants.Player1Piece ? RedPieceColor : YellowPieceColor;
                            Vector3 pos = GetCellPosition(col, row);
                            pos.z = -0.1f;

                            GameObject piece;
                            if (PiecePrefab != null)
                            {
                                piece = Instantiate(PiecePrefab, pos, Quaternion.identity, transform);
                            }
                            else
                            {
                                piece = CreateCircle(CellSize * 0.8f, color);
                                piece.transform.position = pos;
                                piece.transform.SetParent(transform);
                            }
                            _pieceObjects[col, row] = piece;
                        }

                        // Kazanan pozisyon vurgusu
                        if (isWinning && _pieceObjects[col, row] != null)
                        {
                            HighlightWinningPiece(_pieceObjects[col, row]);
                        }
                    }
                    else
                    {
                        // Bos hucre - tasi sil
                        if (_pieceObjects[col, row] != null)
                        {
                            Destroy(_pieceObjects[col, row]);
                            _pieceObjects[col, row] = null;
                        }
                    }
                }
            }
        }

        private void HighlightWinningPiece(GameObject piece)
        {
            // Parlama efekti icin child glow objesi ekle
            if (piece.transform.Find("WinGlow") != null) return;

            var glow = CreateCircle(CellSize * 0.95f, WinHighlightColor);
            glow.name = "WinGlow";
            glow.transform.SetParent(piece.transform);
            glow.transform.localPosition = new Vector3(0, 0, -0.05f);

            // Pulsing animasyon icin WinGlowPulse componenti ekle
            glow.AddComponent<WinGlowPulse>();
        }

        private void OnGameOver()
        {
            RefreshBoard();
        }

        public void ClearBoard()
        {
            if (_pieceObjects == null) return;

            for (int col = 0; col < GameConstants.Cols; col++)
            {
                for (int row = 0; row < GameConstants.Rows; row++)
                {
                    if (_pieceObjects[col, row] != null)
                    {
                        Destroy(_pieceObjects[col, row]);
                        _pieceObjects[col, row] = null;
                    }
                }
            }
        }

        // =========================================================================
        // YARDIMCI FONKSIYONLAR
        // =========================================================================

        private Vector3 GetCellPosition(int col, int row)
        {
            return new Vector3(
                BoardOffsetX + col * CellSize,
                BoardOffsetY + row * CellSize,
                0
            );
        }

        private int WorldToColumn(Vector3 worldPos)
        {
            float relX = worldPos.x - BoardOffsetX + CellSize / 2f;
            int col = Mathf.FloorToInt(relX / CellSize);
            return col;
        }

        private GameObject CreateCircle(float diameter, Color color)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Quad);
            obj.transform.localScale = new Vector3(diameter, diameter, 1);

            var renderer = obj.GetComponent<Renderer>();
            renderer.material = new Material(Shader.Find("Sprites/Default"));
            renderer.material.color = color;

            // Collider'i kaldir (gorsel amacli)
            var collider = obj.GetComponent<Collider>();
            if (collider != null) Destroy(collider);

            return obj;
        }
    }

    // =========================================================================
    // KAZANAN TAS PARLAMA EFEKTI
    // =========================================================================

    public class WinGlowPulse : MonoBehaviour
    {
        private float _time;
        private Renderer _renderer;
        private Color _baseColor;

        private void Start()
        {
            _renderer = GetComponent<Renderer>();
            if (_renderer != null)
                _baseColor = _renderer.material.color;
        }

        private void Update()
        {
            if (_renderer == null) return;

            _time += Time.deltaTime * 3f;
            float pulse = Mathf.Abs(Mathf.Sin(_time)); // 0 ile 1 arasi
            float alpha = 0.3f + pulse * 0.5f;

            Color c = _baseColor;
            c.a = alpha;
            _renderer.material.color = c;

            // Boyut pulsing
            float scale = 1f + pulse * 0.1f;
            transform.localScale = new Vector3(scale, scale, 1f);
        }
    }
}
