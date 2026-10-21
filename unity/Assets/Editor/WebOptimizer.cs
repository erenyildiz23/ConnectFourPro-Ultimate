// =============================================================================
// WebOptimizer.cs - Connect Four Pro Ultimate
// WebGL yayin ayarlarini tek komutla uygular (Unity'nin web optimizasyon onerileri)
// =============================================================================
//
// Menu: Tools > Apply Web Release Settings
// CLI : unity command eval 'UnityEditor.EditorApplication.ExecuteMenuItem("Tools/Apply Web Release Settings");'
//
// Projeye ozel tercihler:
//   * Sikistirma Gzip: oyun LAN'da http:// uzerinden de oynanir; Brotli yalnizca
//     HTTPS/localhost'ta calisir. Flask'in /play rotasi Content-Encoding: gzip gonderir,
//     bu yuzden Decompression Fallback kapali.
//   * Istisnalar "Explicitly Thrown Only": kod try/catch kullanir (JSON, AI iptali).
//   * Kod optimizasyonu (Disk Size LTO) Library/ altinda saklanir ve repoya gecmez;
//     WebGLBuild.Build() bunu her build'de yeniden uygular.

using System.Collections.Generic;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;

namespace ConnectFourPro.EditorTools
{
    public static class WebOptimizer
    {
        public const string TemplateName = "PROJECT:ConnectFour";

        [MenuItem("Tools/Apply Web Release Settings")]
        public static void Apply()
        {
            var target = NamedBuildTarget.WebGL;

            PlayerSettings.companyName = "ConnectFourPro";
            PlayerSettings.productName = "Connect Four Pro Ultimate";
            PlayerSettings.runInBackground = true;
            PlayerSettings.defaultWebScreenWidth = 1280;
            PlayerSettings.defaultWebScreenHeight = 720;

            PlayerSettings.WebGL.template = TemplateName;
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = false;
            PlayerSettings.WebGL.dataCaching = true;
            PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.ExplicitlyThrownExceptionsOnly;
            PlayerSettings.WebGL.debugSymbolMode = WebGLDebugSymbolMode.Off;
            PlayerSettings.WebGL.memoryGrowthMode = WebGLMemoryGrowthMode.Geometric;
            PlayerSettings.WebGL.initialMemorySize = 64;
            PlayerSettings.WebGL.maximumMemorySize = 2048;

            PlayerSettings.stripEngineCode = true;
            PlayerSettings.SetManagedStrippingLevel(target, ManagedStrippingLevel.High);
            PlayerSettings.SetIl2CppCodeGeneration(target, Il2CppCodeGeneration.OptimizeSize);
            PlayerSettings.SetApiCompatibilityLevel(target, ApiCompatibilityLevel.NET_Standard);

            QualitySettings.vSyncCount = 0;
            ApplyCodeOptimization();

            // Kaydetmeden okunan deger yalnizca bellekteki nesnedir; diske yaz
            AssetDatabase.SaveAssets();
            Debug.Log("[WebOptimizer] Uygulandi:\n" + string.Join("\n", Report()));
        }

        /// <summary>
        /// UnityEditor.WebGL.UserBuildSettings.codeOptimization = DiskSizeLTO.
        /// Tur WebGL modulunde oldugu icin yansima ile ayarlanir: modul kurulu
        /// degilse derleme hatasi yerine uyari verilir.
        /// </summary>
        public static void ApplyCodeOptimization()
        {
            var type = System.Type.GetType("UnityEditor.WebGL.UserBuildSettings, UnityEditor.WebGL.Extensions");
            var prop = type?.GetProperty("codeOptimization");
            if (prop == null)
            {
                Debug.LogWarning("[WebOptimizer] WebGL modulu bulunamadi; kod optimizasyonu ayarlanamadi. " +
                                 "Kurulum: unity install-modules --module webgl");
                return;
            }
            try
            {
                var value = System.Enum.Parse(prop.PropertyType, "DiskSizeLTO");
                prop.SetValue(null, value);
            }
            catch (System.ArgumentException)
            {
                Debug.LogWarning("[WebOptimizer] DiskSizeLTO bu Unity surumunde yok; varsayilan kod optimizasyonu kullaniliyor.");
            }
        }

        public static List<string> Report()
        {
            var target = NamedBuildTarget.WebGL;
            return new List<string>
            {
                $"template={PlayerSettings.WebGL.template}",
                $"compressionFormat={PlayerSettings.WebGL.compressionFormat}",
                $"decompressionFallback={PlayerSettings.WebGL.decompressionFallback}",
                $"exceptionSupport={PlayerSettings.WebGL.exceptionSupport}",
                $"dataCaching={PlayerSettings.WebGL.dataCaching}",
                $"stripEngineCode={PlayerSettings.stripEngineCode}",
                $"managedStrippingLevel={PlayerSettings.GetManagedStrippingLevel(target)}",
                $"il2cppCodeGeneration={PlayerSettings.GetIl2CppCodeGeneration(target)}",
                $"apiCompatibilityLevel={PlayerSettings.GetApiCompatibilityLevel(target)}",
                $"memoryGrowthMode={PlayerSettings.WebGL.memoryGrowthMode}",
            };
        }
    }
}
