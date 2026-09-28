const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'Sales Tracker',
    icon: path.join(__dirname, 'src', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC handlers for file operations
ipcMain.handle('save-data', async (event, data) => {
  const { filePath } = await dialog.showSaveDialog(mainWindow, {
    title: 'Save Sales Data',
    defaultPath: 'sales-data.json',
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });

  if (filePath) {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    return { success: true, path: filePath };
  }
  return { success: false };
});

ipcMain.handle('load-data', async () => {
  const { filePaths } = await dialog.showOpenDialog(mainWindow, {
    title: 'Load Sales Data',
    filters: [
      { name: 'JSON Files', extensions: ['json'] },
      { name: 'All Files', extensions: ['*'] }
    ],
    properties: ['openFile']
  });

  if (filePaths && filePaths.length > 0) {
    const data = fs.readFileSync(filePaths[0], 'utf-8');
    return { success: true, data: JSON.parse(data) };
  }
  return { success: false };
});

ipcMain.handle('export-csv', async (event, data) => {
  const { filePath } = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Sales as CSV',
    defaultPath: 'sales-export.csv',
    filters: [
      { name: 'CSV Files', extensions: ['csv'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });

  if (filePath) {
    const headers = ['Date', 'Product', 'Quantity', 'Price', 'Total'];
    const rows = data.map(sale => [
      sale.date,
      sale.productName,
      sale.quantity,
      sale.price.toFixed(2),
      sale.total.toFixed(2)
    ]);
    
    const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
    fs.writeFileSync(filePath, csvContent);
    return { success: true, path: filePath };
  }
  return { success: false };
});
