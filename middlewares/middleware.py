import xmltodict
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from middlewares.forms import UserXMLForm

class XMLParsing(MiddlewareMixin):
    def process_request(self,request):
        if request.content_type in ['application/xml','text/xml']:
            try:
                raw_data=request.body.decode('utf-8')
                parsed_xml=xmltodict.parse(raw_data)
                request.xml_data=parsed_xml
                data=list(parsed_xml())[0] if len(parsed_xml)==1 else parsed_xml
                form=UserXMLForm(data)
                if form.is_valid():
                    request.cleaned_data=form.cleaned_data
                else:
                    return JsonResponse({'Error':"Invalid XML DATA","form_errors":form.errors},status=400)
            except Exception as e:
                return JsonResponse({
                    'error':'Invalid XML',
                    'details':str(e)
                },status=400)
        else:
            request.xml_data=None
            request.cleaned_data=None
