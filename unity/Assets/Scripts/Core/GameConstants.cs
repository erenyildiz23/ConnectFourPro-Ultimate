// =============================================================================
// GameConstants.cs - Connect Four Pro
// Python game_core.py sabitlerinin C# karsiligi
// =============================================================================

namespace ConnectFourPro.Core
{
    public static class GameConstants
    {
        public const int Rows = 6;
        public const int Cols = 7;
        public const int WindowLength = 4;
        public const int Empty = 0;
        public const int Player1Piece = 1;
        public const int Player2Piece = 2;

        // Game States
        public const int StatePlaying = 0;
        public const int StateWin = 1;
        public const int StateDraw = 2;
    }
}
