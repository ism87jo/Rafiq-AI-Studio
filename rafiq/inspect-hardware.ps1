$ErrorActionPreference = 'Stop'
$computer = Get-CimInstance Win32_ComputerSystem
$processors = @(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name)
$videoControllers = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
$nvidia = @()
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $nvidia = @(& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader)
}
[ordered]@{
    RAM_GiB = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
    CPU = $processors
    Display_Adapters = $videoControllers
    NVIDIA_Name_VRAM_MiB_Driver = $nvidia
    Note = 'Read-only report. AdapterRAM is intentionally not used because it can truncate VRAM above 4 GiB.'
} | ConvertTo-Json -Depth 4
