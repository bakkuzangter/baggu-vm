$(function(){
    $('.btn-menu').on('click', function(){
        $(this).toggleClass('on');
        $('.menu-list').fadeToggle();
    });
});

$(function(){
    $('.intro').delay(4000).fadeOut(500, function() {
        $('.header, .main').fadeIn(800);
    });

    $('.first-text').delay(300).animate({
        opacity: 1
    }, 800, function(){
        $('.second-text').delay(600).animate({
            opacity: 1
        });
    });
});
