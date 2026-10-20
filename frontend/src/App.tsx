import { Navigate, Route, Routes } from "react-router";
import { Shell } from "./components/Shell.tsx";
import { AskPage } from "./pages/Ask.tsx";
import { LibraryPage } from "./pages/Library.tsx";
import { OverviewPage } from "./pages/Overview.tsx";
import { SettingsPage } from "./pages/Settings.tsx";
import { SourcePage } from "./pages/Source.tsx";
import { VersionsPage } from "./pages/Versions.tsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<OverviewPage />} />
        <Route path="ask" element={<AskPage />} />
        <Route path="ask/:conversationId" element={<AskPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="documents/:documentId" element={<VersionsPage />} />
        <Route path="sources/:documentId" element={<SourcePage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
