// =============================================================================
// ProjectSetup.cs - Connect Four Pro Ultimate
// Sahne kurulumu, ilk acilista otomatik ayarlar ve komut satiri build'i
// =============================================================================
//
// Menu:
//   Tools > Connect Four > Build Scenes       -> Assets/Scenes/Main.unity
//   Tools > Connect Four > Build WebGL        -> Build/WebGL
//   Tools > Apply Web Release Settings        (WebOptimizer.cs)
//
// Komut satiri (Unity CLI):
//   unity build unity --target WebGL --execute-method ConnectFourPro.EditorTools.ProjectSetup.BuildWebGL

using System.IO;
using System.Linq;
using ConnectFourPro.Game;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ConnectFourPro.EditorTools
{
    [InitializeOnLoad]
    public static class ProjectSetup
    {
        public const string ScenePath = "Assets/Scenes/Main.unity";
        public const string BuildPath = "Build/WebGL";
        private const string FirstRunKey = "ConnectFourPro.FirstRunDone";

        static ProjectSetup()
        {
            // Proje ilk kez acildiginda sahneyi kur ve web ayarlarini uygula
            EditorApplication.delayCall += () =>
            {
                if (Application.isBatchMode || EditorApplication.isPlayingOrWillChangePlaymode)
                    return;
                if (!File.Exists(ScenePath))
                    BuildScenes();
                if (!SessionState.GetBool(FirstRunKey, false) && PlayerSettings.WebGL.template != WebOptimizer.TemplateName)
                {
                    SessionState.SetBool(FirstRunKey, true);
                    WebOptimizer.Apply();
                }
            };
        }

        [MenuItem("Tools/Connect Four/Build Scenes")]
        public static void BuildScenes()
        {
            if (EditorSceneManager.GetActiveScene().isDirty && !Application.isBatchMode
                && !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                return;

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var cameraGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = cameraGo.AddComponent<Camera>();
            cam.orthographic = true;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(26 / 255f, 26 / 255f, 46 / 255f);
            new GameObject("ConnectFourPro").AddComponent<GameBootstrap>();

            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log("[ProjectSetup] Sahne olusturuldu: " + ScenePath);
        }

        [MenuItem("Tools/Connect Four/Build WebGL")]
        public static void BuildWebGLMenu() => Build(exitOnFinish: false);

        /// <summary>Komut satiri build'i (-executeMethod). Hata olursa cikis kodu 1.</summary>
        public static void BuildWebGL() => Build(exitOnFinish: Application.isBatchMode);

        private static void Build(bool exitOnFinish)
        {
            if (!File.Exists(ScenePath))
                BuildScenes();
            WebOptimizer.Apply();

            var options = new BuildPlayerOptions
            {
                scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray(),
                locationPathName = BuildPath,
                target = BuildTarget.WebGL,
                options = BuildOptions.None,
            };
            if (options.scenes.Length == 0)
                options.scenes = new[] { ScenePath };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            var summary = report.summary;
            bool ok = summary.result == BuildResult.Succeeded;
            Debug.Log($"[ProjectSetup] WebGL build: {summary.result}, {summary.totalSize / (1024f * 1024f):0.0} MB, " +
                      $"{summary.totalTime.TotalSeconds:0} sn -> {Path.GetFullPath(BuildPath)}");
            if (exitOnFinish)
                EditorApplication.Exit(ok ? 0 : 1);
        }
    }
}
