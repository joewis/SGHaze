// Swiper.js initialization for card swipe functionality
document.addEventListener('DOMContentLoaded', function() {
    const swiper = new Swiper('.mySwiper', {
        // Enable swipe navigation
        direction: 'horizontal',
        loop: false,
        
        // Pagination dots
        pagination: {
            el: '.swiper-pagination',
            clickable: true,
        },
        
        // Navigation arrows
        navigation: {
            nextEl: '.swiper-button-next',
            prevEl: '.swiper-button-prev',
        },
        
        // Keyboard control
        keyboard: {
            enabled: true,
        },
        
        // Mousewheel control
        mousewheel: {
            invert: false,
        },
        
        // Responsive breakpoints
        breakpoints: {
            // Mobile: show 1 slide at a time
            320: {
                slidesPerView: 1,
                spaceBetween: 10,
            },
            // Tablet and up
            768: {
                slidesPerView: 1,
                spaceBetween: 20,
            },
        },
        
        // Touch/swipe settings
        grabCursor: true,
        touchRatio: 1,
        touchAngle: 45,
        resistanceRatio: 0.85,
    });
    
    console.log('Swiper initialized successfully');
});
