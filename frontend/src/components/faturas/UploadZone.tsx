import { useCallback, useState } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  onFilesUploaded: (files: File[]) => void;
  isProcessing: boolean;
}

export function UploadZone({ onFilesUploaded, isProcessing }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.type === "application/pdf"
    );
    
    if (droppedFiles.length > 0) {
      setFiles(droppedFiles);
      onFilesUploaded(droppedFiles);
    }
  }, [onFilesUploaded]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []).filter(
      file => file.type === "application/pdf"
    );
    
    if (selectedFiles.length > 0) {
      setFiles(selectedFiles);
      onFilesUploaded(selectedFiles);
    }
  }, [onFilesUploaded]);

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "relative rounded-xl border-2 border-dashed p-8 transition-all duration-200",
        isDragging
          ? "border-primary bg-primary/5"
          : "border-border bg-card hover:border-primary/50 hover:bg-primary/5",
        isProcessing && "pointer-events-none opacity-70"
      )}
    >
      <input
        type="file"
        accept=".pdf"
        multiple
        onChange={handleFileInput}
        className="absolute inset-0 cursor-pointer opacity-0"
        disabled={isProcessing}
      />
      
      <div className="flex flex-col items-center justify-center gap-4 text-center">
        {isProcessing ? (
          <>
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-8 w-8 text-primary animate-spin" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Processando faturas...</h3>
              <p className="text-sm text-muted-foreground">
                Extraindo dados de {files.length} arquivo(s)
              </p>
            </div>
          </>
        ) : files.length > 0 ? (
          <>
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
              <FileText className="h-8 w-8 text-success" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">{files.length} arquivo(s) carregado(s)</h3>
              <p className="text-sm text-muted-foreground">
                Arraste mais arquivos ou clique para adicionar
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Upload className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Arraste faturas em PDF aqui</h3>
              <p className="text-sm text-muted-foreground">
                ou clique para selecionar arquivos
              </p>
            </div>
            <div className="flex gap-2 text-xs text-muted-foreground">
              <span className="rounded-full bg-secondary px-3 py-1">PDF</span>
              <span className="rounded-full bg-secondary px-3 py-1">Múltiplos arquivos</span>
              <span className="rounded-full bg-secondary px-3 py-1">Faturas CELESC</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
