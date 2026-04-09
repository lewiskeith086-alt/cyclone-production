const dropzone=document.getElementById("dropzone"),fileInput=document.getElementById("fileInput"),fileName=document.getElementById("fileName"),form=document.getElementById("uploadForm"),statusBox=document.getElementById("uploadStatus"),submitBtn=document.getElementById("submitBtn");
function renderSelectedFiles(){if(!fileInput.files||fileInput.files.length===0){fileName.textContent="";return;}const names=Array.from(fileInput.files).map(f=>f.name);fileName.innerHTML=`<div><strong>${fileInput.files.length}</strong> file(s) selected</div><div class="file-list">${names.map(n=>`<div>${n}</div>`).join("")}</div>`;}
dropzone.addEventListener("dragover",(e)=>{e.preventDefault();dropzone.classList.add("dragover");});
dropzone.addEventListener("dragleave",()=>{dropzone.classList.remove("dragover");});
dropzone.addEventListener("drop",(e)=>{e.preventDefault();dropzone.classList.remove("dragover");if(e.dataTransfer.files.length>0){fileInput.files=e.dataTransfer.files;renderSelectedFiles();}});
fileInput.addEventListener("change",renderSelectedFiles);
form.addEventListener("submit",()=>{submitBtn.disabled=true;submitBtn.textContent="Uploading...";statusBox.textContent="Upload in progress. Please wait...";});
