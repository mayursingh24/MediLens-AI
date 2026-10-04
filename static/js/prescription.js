/**
 * MediLens AI — Premium Prescription Upload & Scanner Interactions
 */

document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("prescription-dropzone");
  const fileInput = document.getElementById("prescription-file-input");
  const browseBtn = document.getElementById("browse-btn");
  const previewBox = document.getElementById("file-preview-box");
  const previewName = document.getElementById("preview-file-name");
  const previewSize = document.getElementById("preview-file-size");
  const changeBtn = document.getElementById("change-file-btn");
  const uploadForm = document.getElementById("prescription-upload-form");
  const submitBtn = document.getElementById("upload-submit-btn");
  const scannerOverlay = document.getElementById("immersive-ai-scanner");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    if (browseBtn) {
      browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
      });
    }

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("drag-over");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        handleFileSelection(fileInput.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFileSelection(fileInput.files[0]);
      }
    });
  }

  if (changeBtn && fileInput) {
    changeBtn.addEventListener("click", () => {
      fileInput.value = "";
      if (previewBox) previewBox.style.display = "none";
      if (submitBtn) submitBtn.setAttribute("disabled", "true");
    });
  }

  function handleFileSelection(file) {
    if (!file) return;
    const allowed = ["image/jpeg", "image/png", "image/jpg", "image/webp", "application/pdf"];
    if (!allowed.includes(file.type) && !file.name.match(/\.(jpg|jpeg|png|webp|pdf)$/i)) {
      showToast("Unsupported format. Please upload JPG, PNG, WEBP, or PDF.", "danger");
      fileInput.value = "";
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      showToast("File size exceeds 16 MB limit.", "danger");
      fileInput.value = "";
      return;
    }

    if (previewBox && previewName) {
      previewName.innerText = file.name;
      if (previewSize) previewSize.innerText = `${(file.size / (1024 * 1024)).toFixed(2)} MB • Ready for analysis`;
      previewBox.style.display = "flex";
    }
    if (submitBtn) {
      submitBtn.removeAttribute("disabled");
    }
  }

  // Camera capture trigger
  const cameraBtn = document.getElementById("camera-trigger-btn");
  if (cameraBtn && fileInput) {
    cameraBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.setAttribute("capture", "environment");
      fileInput.click();
    });
  }

  // Show immersive AI scanner screen with animated stages upon submission
  if (uploadForm && scannerOverlay) {
    uploadForm.addEventListener("submit", () => {
      uploadForm.style.display = "none";
      scannerOverlay.style.display = "block";

      const stages = [
        { id: "stage-vision", delay: 0 },
        { id: "stage-ocr", delay: 1800 },
        { id: "stage-medicine", delay: 3500 },
        { id: "stage-verification", delay: 5200 },
        { id: "stage-context", delay: 6800 },
        { id: "stage-diet", delay: 8400 },
        { id: "stage-careplan", delay: 10200 }
      ];

      stages.forEach((stg, idx) => {
        setTimeout(() => {
          // Mark previous as completed
          if (idx > 0) {
            const prevEl = document.getElementById(stages[idx - 1].id);
            if (prevEl) {
              prevEl.classList.remove("active");
              prevEl.classList.add("completed");
              prevEl.querySelector(".stage-icon").innerText = "✓";
            }
          }
          // Mark current as active
          const currEl = document.getElementById(stg.id);
          if (currEl) {
            currEl.classList.add("active");
            currEl.querySelector(".stage-icon").innerText = "◉";
          }
        }, stg.delay);
      });
    });
  }
});
