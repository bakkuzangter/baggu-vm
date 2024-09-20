$(function(){
    $('.btn-menu').on('click', function(){
        $(this).toggleClass('on');
        $('.menu-list').fadeToggle();
    });
});


$(function(){
    const loggedInUser = "{{ user }}";  // Flask에서 전달한 사용자 정보

    if (!sessionStorage.getItem(`introDisplayed_${loggedInUser}`)) {
        // 로그인 후 처음으로 intro를 보여줌
        $('.intro').show().delay(3000).fadeOut(400, function() {
            $('.header, .main').fadeIn(700);
        });

        $('.first-text > img').delay(200).animate({
            opacity: 1
        }, 600, function(){
            $('.second-text').delay(500).animate({
                opacity: 1
            });
        });

        // 세션 스토리지에 intro 표시 여부 저장
        sessionStorage.setItem(`introDisplayed_${loggedInUser}`, true);
    } else {
        // 이미 intro를 본 사용자에게는 바로 메인 화면을 보여줌
        $('.header, .main').show();
    }
});


/* banner */
var swiper = new Swiper(".mySwiper", {
    spaceBetween: 30,
    centeredSlides: true,
    autoplay: {
      delay: 4000,
      disableOnInteraction: false,
    },
    pagination: {
      el: ".swiper-pagination",
      clickable: true,
    },
    navigation: {
      nextEl: ".swiper-button-next",
      prevEl: ".swiper-button-prev",
    },
  });
