const bottle = document.querySelector(".product-bottle img");

if (bottle) {
    window.addEventListener("scroll", () => {
        const offset = window.scrollY * 0.15;
        bottle.style.transform = `translateY(${offset}px)`;
    });
}