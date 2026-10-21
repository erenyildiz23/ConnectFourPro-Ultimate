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
