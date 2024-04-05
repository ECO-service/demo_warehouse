(function($){
    $(document).ready(function(){
        $('input[type="submit"]').on('click', function(){
            if(confirm("Bạn có chắc muốn lưu thay đổi này không?")){
                return true;
            }
            return false;
        });
    });
})(django.jQuery);

