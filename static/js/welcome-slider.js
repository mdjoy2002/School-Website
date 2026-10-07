(() => {
    const modal = document.getElementById('welcomeSlider');
    const imageElement = document.getElementById('welcomeSliderImage');
    const titleElement = document.getElementById('welcomeSliderTitle');
    const counterElement = document.getElementById('welcomeSliderCounter');
    const closeButton = document.getElementById('welcomeSliderClose');
    const dataElement = document.getElementById('welcome-slider-images');

    if (!modal || !imageElement || !titleElement || !counterElement || !closeButton || !dataElement) {
        return;
    }

    const images = JSON.parse(dataElement.textContent);
    if (!images.length) {
        return;
    }

    const navigationEntries = performance.getEntriesByType('navigation');
    const navigationType = navigationEntries.length ? navigationEntries[0].type : 'navigate';
    const isReload = navigationType === 'reload';
    const hasSameOriginReferrer = document.referrer && new URL(document.referrer).origin === window.location.origin;

    if (!isReload && hasSameOriginReferrer) {
        modal.hidden = true;
        return;
    }

    let currentIndex = 0;
    let advancing = false;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    function closePopup() {
        modal.hidden = true;
        document.body.style.overflow = previousOverflow;
    }

    function updateImage(index) {
        const item = images[index];
        imageElement.alt = item.title || 'Welcome image';
        titleElement.textContent = item.title || '';
        titleElement.hidden = !item.title;
        counterElement.textContent = `${index + 1} / ${images.length}`;
        closeButton.setAttribute(
            'aria-label',
            index < images.length - 1 ? 'Next image' : 'Close popup'
        );

        imageElement.onload = () => {
            imageElement.style.opacity = '1';
            advancing = false;
            if (index + 1 < images.length) {
                const nextImage = new Image();
                nextImage.src = images[index + 1].url;
            }
        };
        imageElement.onerror = () => {
            advancing = false;
            advance();
        };
        imageElement.src = item.url;
    }

    function advance() {
        if (advancing) {
            return;
        }
        advancing = true;
        imageElement.style.opacity = '0';

        window.setTimeout(() => {
            const nextIndex = currentIndex + 1;
            if (nextIndex >= images.length) {
                closePopup();
                return;
            }
            currentIndex = nextIndex;
            updateImage(currentIndex);
        }, 150);
    }

    closeButton.addEventListener('click', advance);
    updateImage(currentIndex);
})();
