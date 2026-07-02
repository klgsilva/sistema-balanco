(function () {
    const appShell = document.querySelector("[data-app-shell]");
    const toggle = document.querySelector("[data-menu-toggle]");
    const menu = document.querySelector("[data-menu]");
    const menuBackdrop = document.querySelector("[data-menu-backdrop]");
    const sidebarCollapse = document.querySelector("[data-sidebar-collapse]");
    const sidebarCollapsedKey = "inventario:sidebar-collapsed";

    if (appShell && localStorage.getItem(sidebarCollapsedKey) === "1") {
        appShell.classList.add("sidebar-collapsed");
    }
    if (sidebarCollapse && appShell) {
        sidebarCollapse.addEventListener("click", () => {
            appShell.classList.toggle("sidebar-collapsed");
            localStorage.setItem(sidebarCollapsedKey, appShell.classList.contains("sidebar-collapsed") ? "1" : "0");
        });
    }
    if (toggle && menu) {
        let menuScrollY = 0;
        const closeMenu = () => {
            if (!menu.classList.contains("open")) return;
            menu.classList.remove("open");
            toggle.classList.remove("open");
            toggle.setAttribute("aria-expanded", "false");
            if (menuBackdrop) menuBackdrop.classList.remove("open");
            document.body.classList.remove("menu-locked");
            document.body.style.top = "";
            window.scrollTo(0, menuScrollY);
        };
        toggle.addEventListener("click", () => {
            if (menu.classList.contains("open")) {
                closeMenu();
                return;
            }
            menuScrollY = window.scrollY;
            document.body.classList.add("menu-locked");
            document.body.style.top = `-${menuScrollY}px`;
            menu.classList.add("open");
            toggle.classList.add("open");
            toggle.setAttribute("aria-expanded", "true");
            if (menuBackdrop) menuBackdrop.classList.add("open");
        });
        if (menuBackdrop) menuBackdrop.addEventListener("click", closeMenu);
        menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
    }

    const scrollKey = `inventario:scroll:${window.location.pathname}`;
    const savedScroll = sessionStorage.getItem(scrollKey);
    if (savedScroll !== null) {
        sessionStorage.removeItem(scrollKey);
        requestAnimationFrame(() => {
            window.scrollTo(0, Number(savedScroll) || 0);
        });
    }
    document.querySelectorAll("form[data-restore-scroll]").forEach((form) => {
        form.addEventListener("submit", () => {
            sessionStorage.setItem(scrollKey, String(window.scrollY));
        });
    });

    document.querySelectorAll("form[data-dirty-form]").forEach((form) => {
        const submitButton = form.querySelector("[data-dirty-submit]");
        if (!submitButton) return;
        const fields = Array.from(form.querySelectorAll("input, select, textarea"))
            .filter((field) => field.type !== "hidden" && !field.disabled && !field.readOnly);
        const snapshot = () => fields.map((field) => (
            field.type === "checkbox" || field.type === "radio" ? field.checked : field.value
        )).join("|");
        const initialState = snapshot();
        const syncDirtyState = () => {
            submitButton.disabled = snapshot() === initialState;
        };
        fields.forEach((field) => {
            field.addEventListener("input", syncDirtyState);
            field.addEventListener("change", syncDirtyState);
        });
        form.addEventListener("submit", () => {
            submitButton.disabled = false;
        });
        syncDirtyState();
    });

    document.querySelectorAll("[data-filter-location]").forEach((filterLocation) => {
        const form = filterLocation.closest("form");
        const filterCorridor = form ? form.querySelector("[data-filter-corridor]") : null;
        const filterCorridorField = form ? form.querySelector("[data-filter-corridor-field]") : null;
        const syncFilterCorridor = () => {
            if (!filterCorridor) return;
            const warehouseSelected = filterLocation.value === "warehouse";
            if (warehouseSelected) {
                filterCorridor.value = "";
            }
            filterCorridor.disabled = warehouseSelected;
            if (filterCorridorField) {
                filterCorridorField.classList.toggle("is-disabled", warehouseSelected);
                filterCorridorField.title = warehouseSelected ? "Deposito nao separa por corredor." : "";
            }
        };
        filterLocation.addEventListener("change", syncFilterCorridor);
        syncFilterCorridor();
    });

    const barcodeInput = document.querySelector("[data-barcode-input]");
    const launchStore = document.querySelector("[data-launch-store]");
    const launchCorridor = document.querySelector("[data-launch-corridor]");
    const stockLocation = document.querySelector("[data-stock-location]");
    const productFields = document.querySelector("[data-product-fields]");
    const productActions = document.querySelectorAll("[data-product-action]");
    const corridorTotalPanel = document.querySelector("[data-corridor-total-panel]");
    const corridorSavedItems = document.querySelector("[data-corridor-saved-items]");
    const corridorPreviewCost = document.querySelector("[data-corridor-preview-cost]");
    const syncLaunchStep = () => {
        if (!launchCorridor || !productFields || !stockLocation) return;
        const hasStore = !launchStore || Boolean(launchStore.value);
        if (!hasStore) {
            launchCorridor.value = "";
        }
        launchCorridor.disabled = !hasStore;
        const hasChoice = hasStore && Boolean(launchCorridor.value);
        const isWarehouse = launchCorridor.value === "__warehouse__";
        stockLocation.value = isWarehouse ? "warehouse" : "store";
        productFields.hidden = !hasChoice;
        productActions.forEach((item) => {
            item.hidden = !hasChoice;
            if ("disabled" in item) item.disabled = !hasChoice;
        });
        if (corridorTotalPanel) {
            corridorTotalPanel.hidden = !hasChoice;
        }
        if (hasChoice && barcodeInput && document.activeElement === launchCorridor) {
            barcodeInput.focus();
        }
        updateCost();
    };
    if (launchCorridor) {
        launchCorridor.addEventListener("change", syncLaunchStep);
    }
    if (launchStore) {
        launchStore.addEventListener("change", () => {
            const baseUrl = launchStore.dataset.launchUrl || window.location.pathname;
            if (launchStore.value) {
                window.location = `${baseUrl}?loja_id=${encodeURIComponent(launchStore.value)}`;
                return;
            }
            window.location = baseUrl;
        });
    }

    const salePrice = document.querySelector("[data-sale-price]");
    const margin = document.querySelector("[data-margin]");
    const quantity = document.querySelector("[data-quantity]");
    const measureType = document.querySelector("[data-measure-type]");
    const measureTitle = document.querySelector("[data-measure-title]");
    const quantityTitle = document.querySelector("[data-quantity-title]");
    const costPreview = document.querySelector("[data-cost-preview]");
    const lineSaleTotal = document.querySelector("[data-line-sale-total]");
    const lineCostTotal = document.querySelector("[data-line-cost-total]");
    const syncMeasureOptions = (isWarehouse) => {
        if (!measureType) return;
        const context = isWarehouse ? "warehouse" : "store";
        let selectedIsValid = false;
        Array.from(measureType.options).forEach((option) => {
            const isValid = option.dataset.measureContext === context;
            option.hidden = !isValid;
            option.disabled = !isValid;
            if (option.selected && isValid) {
                selectedIsValid = true;
            }
        });
        if (!selectedIsValid) {
            const nextOption = Array.from(measureType.options).find((option) => option.dataset.measureContext === context);
            if (nextOption) {
                measureType.value = nextOption.value;
            }
        }
        if (measureTitle) {
            measureTitle.textContent = isWarehouse ? "Tipo de volume" : "Tipo";
        }
        if (quantityTitle) {
            quantityTitle.textContent = isWarehouse ? "Quantidade de caixas/fardos" : "Quantidade / peso";
        }
    };
    const parseMoney = (value) => {
        let normalized = String(value || "0").replace("R$", "").replace(/\s/g, "");
        if (normalized.includes(",")) {
            normalized = normalized.replace(/\./g, "").replace(",", ".");
        } else if (normalized.includes(".")) {
            const parts = normalized.split(".");
            if (parts.length > 2 || parts[parts.length - 1].length === 3) {
                normalized = parts.join("");
            }
        }
        const number = Number(normalized);
        return Number.isFinite(number) ? number : 0;
    };
    const parseQuantity = (value) => {
        let normalized = String(value || "0").replace(/\s/g, "");
        if (measureType && measureType.value === "kg") {
            if (normalized.includes(",")) {
                const index = normalized.lastIndexOf(",");
                const before = normalized.slice(0, index);
                const after = normalized.slice(index + 1);
                if (before.includes(".") && /^0+$/.test(after)) {
                    normalized = before;
                } else {
                    normalized = normalized.replace(/\./g, "").replace(",", ".");
                }
            }
        } else {
            normalized = String(parseMoney(normalized));
        }
        const number = Number(normalized);
        return Number.isFinite(number) ? number : 0;
    };
    const formatBRL = (value) => value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    const updateCost = () => {
        const selectedBucket = launchCorridor ? launchCorridor.selectedOptions[0] : null;
        const isWarehouse = launchCorridor && launchCorridor.value === "__warehouse__";
        syncMeasureOptions(isWarehouse);
        const savedCost = selectedBucket ? parseMoney(selectedBucket.dataset.savedCost) : 0;
        const savedItems = selectedBucket ? Number(selectedBucket.dataset.savedItems || 0) : 0;
        const sale = salePrice ? parseMoney(salePrice.value) : 0;
        const qty = quantity ? parseQuantity(quantity.value) : 1;
        const cost = margin ? sale * (1 - (Number(margin.value || 0) / 100)) : 0;
        if (costPreview) {
            costPreview.value = cost > 0 ? formatBRL(cost) : "";
        }
        if (lineSaleTotal) {
            lineSaleTotal.textContent = formatBRL(Math.max(0, sale * qty));
        }
        if (lineCostTotal) {
            lineCostTotal.textContent = formatBRL(Math.max(0, cost * qty));
        }
        if (corridorSavedItems) {
            corridorSavedItems.textContent = String(savedItems);
        }
        if (corridorPreviewCost) {
            corridorPreviewCost.textContent = formatBRL(Math.max(0, savedCost + (cost * qty)));
        }
    };
    if (salePrice && margin) {
        salePrice.addEventListener("input", updateCost);
        margin.addEventListener("input", updateCost);
        if (quantity) quantity.addEventListener("input", updateCost);
        if (measureType) measureType.addEventListener("change", updateCost);
        updateCost();
    }
    syncLaunchStep();

    const origin = document.querySelector("[data-origin]");
    if (origin && margin) {
        origin.addEventListener("change", () => {
            if (origin.value === "third_party" && (!margin.value || margin.value === "20")) {
                margin.value = "30";
                updateCost();
            }
        });
    }

    const scanButton = document.querySelector("[data-scan-barcode]");
    const scanner = document.querySelector("[data-scanner]");
    const video = document.querySelector("[data-scanner-video]");
    const stopButton = document.querySelector("[data-stop-scan]");
    const status = document.querySelector("[data-scanner-status]");
    const scanFile = document.querySelector("[data-scan-file]");
    const html5ReaderContainer = document.querySelector("[data-html5-reader]");
    let stream = null;
    let scanning = false;
    let zxingReader = null;
    let html5Scanner = null;
    let quaggaRunning = false;
    let quaggaDetectedHandler = null;

    const stopScan = () => {
        scanning = false;
        if (quaggaRunning && window.Quagga) {
            if (quaggaDetectedHandler && Quagga.offDetected) {
                Quagga.offDetected(quaggaDetectedHandler);
            }
            Quagga.stop();
            quaggaRunning = false;
            quaggaDetectedHandler = null;
        }
        if (html5Scanner) {
            html5Scanner.stop().then(() => {
                if (html5Scanner && html5Scanner.clear) html5Scanner.clear();
                html5Scanner = null;
            }).catch(() => {
                html5Scanner = null;
            });
        }
        if (zxingReader && zxingReader.reset) zxingReader.reset();
        zxingReader = null;
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = null;
        if (video) video.srcObject = null;
        if (video) video.hidden = true;
        if (scanner) scanner.hidden = true;
    };

    const fillBarcode = (code) => {
        if (!code || !barcodeInput) return;
        barcodeInput.value = String(code).replace(/\D/g, "").slice(0, 13);
        stopScan();
        barcodeInput.focus();
    };

    if (barcodeInput) {
        barcodeInput.addEventListener("input", () => {
            barcodeInput.value = barcodeInput.value.replace(/\D/g, "").slice(0, 13);
        });
    }

    const scanLoop = async (detector) => {
        if (!scanning) return;
        try {
            const codes = await detector.detect(video);
            if (codes.length) {
                fillBarcode(codes[0].rawValue);
                return;
            }
        } catch (error) {
            if (status) status.textContent = "Nao foi possivel ler agora. Tente aproximar a camera.";
        }
        requestAnimationFrame(() => scanLoop(detector));
    };

    const openNativeCamera = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Camera indisponivel neste navegador.");
        }
        scanner.hidden = false;
        if (html5ReaderContainer) html5ReaderContainer.innerHTML = "";
        if (status) status.textContent = "Abrindo camera...";
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: false,
        });
        video.srcObject = stream;
        video.hidden = false;
        await video.play();
        scanning = true;
        if (status) status.textContent = "Camera aberta. Aponte para o codigo de barras.";
    };

    const scanWithNativeCamera = async () => {
        await openNativeCamera();
        if (!("BarcodeDetector" in window)) {
            throw new Error("BarcodeDetector indisponivel.");
        }
        const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "upc_a", "upc_e"] });
        scanLoop(detector);
    };

    const scanWithQuaggaLive = async () => new Promise((resolve, reject) => {
        if (!window.Quagga || !html5ReaderContainer) {
            reject(new Error("Quagga ao vivo indisponivel."));
            return;
        }
        scanner.hidden = false;
        if (video) video.hidden = true;
        html5ReaderContainer.innerHTML = "";
        if (status) status.textContent = "Abrindo camera do leitor. Autorize o uso da camera.";
        Quagga.init({
            inputStream: {
                type: "LiveStream",
                target: html5ReaderContainer,
                constraints: {
                    facingMode: "environment",
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            },
            locator: {
                patchSize: "medium",
                halfSample: true,
            },
            numOfWorkers: 0,
            frequency: 10,
            decoder: {
                readers: [
                    "ean_reader",
                    "ean_8_reader",
                    "upc_reader",
                    "upc_e_reader",
                    "code_128_reader",
                    "code_39_reader",
                ],
            },
            locate: true,
        }, (error) => {
            if (error) {
                reject(error);
                return;
            }
            scanning = true;
            quaggaRunning = true;
            if (status) status.textContent = "Aponte o codigo inteiro dentro do quadro.";
            quaggaDetectedHandler = (result) => {
                const code = result && result.codeResult && result.codeResult.code;
                if (code) fillBarcode(code);
            };
            Quagga.onDetected(quaggaDetectedHandler);
            Quagga.start();
            resolve();
        });
    });

    const scanWithHtml5Qrcode = async () => {
        if (!window.Html5Qrcode || !html5ReaderContainer) {
            throw new Error("Html5Qrcode indisponivel.");
        }
        if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
            throw new Error("Camera ao vivo precisa de HTTPS.");
        }
        scanner.hidden = false;
        if (video) video.hidden = true;
        if (status) status.textContent = "Aponte a camera para o codigo. Mantenha as barras dentro do quadro.";
        scanning = true;
        html5Scanner = new Html5Qrcode(html5ReaderContainer.id);
        const formats = window.Html5QrcodeSupportedFormats ? [
            Html5QrcodeSupportedFormats.EAN_13,
            Html5QrcodeSupportedFormats.EAN_8,
            Html5QrcodeSupportedFormats.UPC_A,
            Html5QrcodeSupportedFormats.UPC_E,
            Html5QrcodeSupportedFormats.CODE_128,
            Html5QrcodeSupportedFormats.CODE_39,
        ] : undefined;
        await html5Scanner.start(
            { facingMode: "environment" },
            {
                fps: 12,
                qrbox: (viewfinderWidth, viewfinderHeight) => ({
                    width: Math.floor(viewfinderWidth * 0.86),
                    height: Math.max(110, Math.floor(viewfinderHeight * 0.34)),
                }),
                aspectRatio: 1.777778,
                formatsToSupport: formats,
            },
            (decodedText) => fillBarcode(decodedText),
            () => {}
        );
    };

    const scanWithZXingVideo = async () => {
        if (!window.ZXing || !ZXing.BrowserMultiFormatReader || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Leitor ao vivo indisponivel.");
        }
        scanner.hidden = false;
        scanning = true;
        if (status) status.textContent = "Aponte a camera para o codigo de barras.";
        zxingReader = new ZXing.BrowserMultiFormatReader();
        await zxingReader.decodeFromVideoDevice(null, video, (result, error) => {
            if (!scanning) return;
            if (result) {
                fillBarcode(result.text || (result.getText ? result.getText() : ""));
            } else if (error && error.name && error.name !== "NotFoundException" && status) {
                status.textContent = "Tentando ler. Aproxime e mantenha o codigo centralizado.";
            }
        });
    };

    const readBarcodeWithQuagga = (imageUrl) => new Promise((resolve, reject) => {
        if (!window.Quagga || !Quagga.decodeSingle) {
            reject(new Error("Quagga indisponivel."));
            return;
        }
        Quagga.decodeSingle({
            src: imageUrl,
            numOfWorkers: 0,
            locate: true,
            inputStream: {
                size: 1600,
                singleChannel: false,
            },
            decoder: {
                readers: [
                    "ean_reader",
                    "ean_8_reader",
                    "upc_reader",
                    "upc_e_reader",
                    "code_128_reader",
                    "code_39_reader",
                ],
            },
        }, (result) => {
            const code = result && result.codeResult && result.codeResult.code;
            if (code) {
                resolve(code);
                return;
            }
            reject(new Error("Codigo nao encontrado pelo Quagga."));
        });
    });

    const readBarcodeWithZXing = async (imageUrl) => {
        if (!window.ZXing || !ZXing.BrowserMultiFormatReader) {
            throw new Error("ZXing indisponivel.");
        }
        const hints = new Map();
        if (ZXing.DecodeHintType && ZXing.BarcodeFormat) {
            hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
                ZXing.BarcodeFormat.EAN_13,
                ZXing.BarcodeFormat.EAN_8,
                ZXing.BarcodeFormat.UPC_A,
                ZXing.BarcodeFormat.UPC_E,
                ZXing.BarcodeFormat.CODE_128,
                ZXing.BarcodeFormat.CODE_39,
            ]);
            hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
        }
        const reader = new ZXing.BrowserMultiFormatReader(hints);
        const result = await reader.decodeFromImageUrl(imageUrl);
        if (reader.reset) reader.reset();
        return result && (result.text || (result.getText ? result.getText() : ""));
    };

    const readBarcodeFromPhoto = async (file) => {
        const imageUrl = URL.createObjectURL(file);
        try {
            try {
                return await readBarcodeWithQuagga(imageUrl);
            } catch (quaggaError) {
                return await readBarcodeWithZXing(imageUrl);
            }
        } finally {
            URL.revokeObjectURL(imageUrl);
        }
    };

    const openPhotoScanner = () => {
        if (!scanFile) {
            alert("Este navegador nao liberou a camera. Use o campo manual.");
            return;
        }
        scanFile.value = "";
        scanFile.click();
    };

    if (scanButton) {
        scanButton.addEventListener("click", async () => {
            if (!launchCorridor || !launchCorridor.value) {
                alert("Escolha o corredor ou deposito antes de usar a camera.");
                return;
            }
            const needsSecureCamera = !window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1";
            if (needsSecureCamera) {
                const secureUrl = `https://${location.hostname}:5443${location.pathname}${location.search}`;
                if (confirm("Para ler codigo de barras ao vivo, preciso abrir o modo seguro da camera. Abrir agora?")) {
                    window.location.href = secureUrl;
                    return;
                }
            }
            const canUseLiveCamera = navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
            try {
                if ("BarcodeDetector" in window && canUseLiveCamera) {
                    await scanWithNativeCamera();
                    return;
                }
                if (canUseLiveCamera && window.Quagga) {
                    await scanWithQuaggaLive();
                    return;
                }
                if (canUseLiveCamera && window.Html5Qrcode) {
                    await scanWithHtml5Qrcode();
                    return;
                }
                if (canUseLiveCamera) {
                    await scanWithZXingVideo();
                    return;
                }
                openPhotoScanner();
            } catch (error) {
                stopScan();
                if (status) status.textContent = "Nao consegui abrir a camera ao vivo.";
                alert("Nao consegui abrir a camera ao vivo. Confira a permissao da camera no navegador.");
            }
        });
    }
    if (scanFile) {
        scanFile.addEventListener("change", async () => {
            const file = scanFile.files && scanFile.files[0];
            if (!file) return;
            try {
                if (scanner) scanner.hidden = false;
                if (status) status.textContent = "Lendo a foto do codigo de barras...";
                const code = await readBarcodeFromPhoto(file);
                if (!code) throw new Error("Codigo nao encontrado.");
                fillBarcode(code);
            } catch (error) {
                if (scanner) scanner.hidden = true;
                alert("Nao consegui ler o codigo da foto. Tente aproximar melhor ou digite no campo manual.");
            }
        });
    }
    if (stopButton) stopButton.addEventListener("click", stopScan);
})();
