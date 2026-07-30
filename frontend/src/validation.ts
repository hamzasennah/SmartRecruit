export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];

export type FileLimits = {
  maxUploadMb: number;
  maxTotalUploadMb: number;
};

export const DEFAULT_FILE_LIMITS: FileLimits = {
  maxUploadMb: Number(import.meta.env.VITE_MAX_UPLOAD_MB || 20),
  maxTotalUploadMb: Number(import.meta.env.VITE_MAX_TOTAL_UPLOAD_MB || 100),
};

export function validateSelection(jobFile: File | null, cvFiles: File[], limits: FileLimits = DEFAULT_FILE_LIMITS): string | null {
  if (!jobFile || cvFiles.length === 0) {
    return "Ajoutez une fiche de poste et au moins un CV.";
  }
  const allFiles = [jobFile, ...cvFiles];
  const maxBytes = limits.maxUploadMb * 1024 * 1024;
  const maxTotalBytes = limits.maxTotalUploadMb * 1024 * 1024;
  for (const file of allFiles) {
    if (!hasSupportedExtension(file.name)) {
      return `Format non supporte: ${file.name}`;
    }
    if (file.size > maxBytes) {
      return `Fichier trop volumineux: ${file.name}`;
    }
  }
  const total = allFiles.reduce((sum, file) => sum + file.size, 0);
  if (total > maxTotalBytes) {
    return "Taille cumulee des fichiers trop volumineuse.";
  }
  return null;
}

export function hasSupportedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

// Role dans le projet:
// Ce fichier valide localement la selection de fichiers. Il duplique les limites utilisateur visibles avant que le backend applique ses propres garde-fous.
