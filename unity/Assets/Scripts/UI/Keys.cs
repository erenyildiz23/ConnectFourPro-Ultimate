// =============================================================================
// Keys.cs - Connect Four Pro Ultimate
// Klavye kisayollari: yeni Input System varsa onu, yoksa eski Input'u kullanir
// =============================================================================

using UnityEngine;

namespace ConnectFourPro.UI
{
    public static class Keys
    {
        public static bool EnterPressed()
        {
#if CF4_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            return k != null && (k.enterKey.wasPressedThisFrame || k.numpadEnterKey.wasPressedThisFrame);
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter);
#else
            return false;
#endif
        }

        /// <summary>1-7 (ust sira veya sayi tus takimi) -> sutun 0..6; basilmadiysa -1.</summary>
        public static int ColumnPressed()
        {
#if CF4_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            if (k == null)
                return -1;
            if (k.digit1Key.wasPressedThisFrame || k.numpad1Key.wasPressedThisFrame) return 0;
            if (k.digit2Key.wasPressedThisFrame || k.numpad2Key.wasPressedThisFrame) return 1;
            if (k.digit3Key.wasPressedThisFrame || k.numpad3Key.wasPressedThisFrame) return 2;
            if (k.digit4Key.wasPressedThisFrame || k.numpad4Key.wasPressedThisFrame) return 3;
            if (k.digit5Key.wasPressedThisFrame || k.numpad5Key.wasPressedThisFrame) return 4;
            if (k.digit6Key.wasPressedThisFrame || k.numpad6Key.wasPressedThisFrame) return 5;
            if (k.digit7Key.wasPressedThisFrame || k.numpad7Key.wasPressedThisFrame) return 6;
            return -1;
#elif ENABLE_LEGACY_INPUT_MANAGER
            for (int i = 0; i < 7; i++)
                if (Input.GetKeyDown(KeyCode.Alpha1 + i) || Input.GetKeyDown(KeyCode.Keypad1 + i))
                    return i;
            return -1;
#else
            return -1;
#endif
        }

        public static bool BackPressed()
        {
#if CF4_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            return k != null && k.escapeKey.wasPressedThisFrame;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(KeyCode.Escape);
#else
            return false;
#endif
        }

        public static bool TabPressed()
        {
#if CF4_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            return k != null && k.tabKey.wasPressedThisFrame;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(KeyCode.Tab);
#else
            return false;
#endif
        }
    }
}
