import { describe, expect, it } from "vitest";
import { hasSupportedExtension, validateSelection } from "./validation";

function file(name: string, size = 10): File {
  return new File(["x".repeat(size)], name);
}

describe("validateSelection", () => {
  it("requires a job file and at least one CV", () => {
    expect(validateSelection(null, [])).toContain("fiche de poste");
  });

  it("does not impose an arbitrary CV count limit", () => {
    const result = validateSelection(file("job.txt"), Array.from({ length: 30 }, (_, index) => file(`cv${index}.txt`)), {
      maxUploadMb: 1,
      maxTotalUploadMb: 10,
    });
    expect(result).toBeNull();
  });

  it("enforces file extensions", () => {
    expect(hasSupportedExtension("cv.exe")).toBe(false);
    expect(hasSupportedExtension("cv.pdf")).toBe(true);
  });

  it("enforces total size", () => {
    const result = validateSelection(file("job.txt", 6), [file("cv.txt", 6)], {
      maxUploadMb: 1,
      maxTotalUploadMb: 0.00001,
    });
    expect(result).toContain("Taille cumulee");
  });
});

// Role dans le projet:
// Ce fichier verifie la validation frontend des fichiers. Il protege les messages et limites affiches avant l'envoi au backend.
