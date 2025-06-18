import xml.etree.ElementTree as ET
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa
import io
# Create your views here.
def find_section_by_code(root, code_value, ns):
    for section in root.findall('.//hl7:section', ns):
        code = section.find('hl7:code', ns)
        if code is not None and code.attrib.get('code') == code_value:
            return section
    return None


def upload_xml(request):
    if request.method == 'POST' and 'xml_file' in request.FILES:
        xml_file = request.FILES['xml_file']
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            ns = {'hl7': 'urn:hl7-org:v3'}

            # Initialize variables
            given = family = gender = birth_time = race = ethnicity = language = address = ''

            # Extract patient demographics
            patient_role = root.find('.//hl7:recordTarget/hl7:patientRole', ns)
            if patient_role is not None:
                name_el = patient_role.find('.//hl7:patient/hl7:name', ns)
                if name_el is not None:
                    given = name_el.find('hl7:given', ns).text if name_el.find('hl7:given', ns) is not None else ''
                    family = name_el.find('hl7:family', ns).text if name_el.find('hl7:family', ns) is not None else ''
                gender_el = patient_role.find('.//hl7:patient/hl7:administrativeGenderCode', ns)
                gender = gender_el.attrib.get('code', '') if gender_el is not None else ''
                birth_el = patient_role.find('.//hl7:patient/hl7:birthTime', ns)
                birth_time = birth_el.attrib.get('value', '') if birth_el is not None else ''
                race_el = patient_role.find('.//hl7:patient/hl7:raceCode', ns)
                race = race_el.attrib.get('displayName', '') if race_el is not None else ''
                ethnicity_el = patient_role.find('.//hl7:patient/hl7:ethnicGroupCode', ns)
                ethnicity = ethnicity_el.attrib.get('displayName', '') if ethnicity_el is not None else ''
                lang_el = patient_role.find('.//hl7:languageCommunication/hl7:languageCode', ns)
                language = lang_el.attrib.get('code', '') if lang_el is not None else ''
                addr_el = patient_role.find('hl7:addr', ns)
                if addr_el is not None:
                    address = ', '.join([child.text for child in addr_el if child is not None and child.text])

            # SECTIONS
            medications = []
            allergies = []
            diagnostics = []

            # Medications Section
            med_section = find_section_by_code(root, '10160-0', ns)
            if med_section is not None:
                for entry in med_section.findall('.//hl7:entry/hl7:substanceAdministration', ns):
                    med = {}
                    name_el = entry.find('.//hl7:manufacturedMaterial/hl7:code', ns)
                    if name_el is not None:
                        med['name'] = name_el.attrib.get('displayName', '')
                        med['code'] = name_el.attrib.get('code', '')
                    eff = entry.find('hl7:effectiveTime', ns)
                    if eff is not None:
                        low = eff.find('hl7:low', ns)
                        high = eff.find('hl7:high', ns)
                        med['start'] = low.attrib.get('value', '') if low is not None else ''
                        med['end'] = high.attrib.get('value', '') if high is not None else ''
                    medications.append(med)

            # Allergies Section
            allergy_section = find_section_by_code(root, '48765-2', ns)
            if allergy_section is not None:
                for entry in allergy_section.findall('.//hl7:entry', ns):
                    allergy = {}
                    obs = entry.find('.//hl7:observation', ns)
                    if obs is not None:
                        code_el = obs.find('hl7:code', ns)
                        val_el = obs.find('hl7:value', ns)
                        eff = obs.find('hl7:effectiveTime', ns)
                        allergy['substance'] = code_el.attrib.get('displayName', '') if code_el is not None else ''
                        allergy['reaction'] = val_el.attrib.get('displayName', '') if val_el is not None else ''
                        allergy['code'] = code_el.attrib.get('code', '') if code_el is not None else ''
                        allergy['date'] = eff.find('hl7:low', ns).attrib.get('value', '') if eff is not None and eff.find('hl7:low', ns) is not None else ''
                        allergies.append(allergy)

            # Diagnostic Results Section
            diag_section = find_section_by_code(root, '30954-2', ns)
            if diag_section is not None:
                for org in diag_section.findall('.//hl7:organizer', ns):
                    diag = {}
                    code_el = org.find('hl7:code', ns)
                    if code_el is not None:
                        diag['test_name'] = code_el.attrib.get('displayName', '')
                        diag['test_code'] = code_el.attrib.get('code', '')
                    eff = org.find('hl7:effectiveTime', ns)
                    if eff is not None:
                        low = eff.find('hl7:low', ns)
                        diag['date'] = low.attrib.get('value', '') if low is not None else ''
                    comp = org.find('hl7:component/hl7:observation/hl7:value', ns)
                    if comp is not None:
                        diag['value'] = comp.attrib.get('value', '')
                        diag['unit'] = comp.attrib.get('unit', '')
                    diagnostics.append(diag)

            # Build context
            context = {
                'name': f"{given} {family}",
                'gender': gender,
                'birth_time': birth_time,
                'race': race,
                'ethnicity': ethnicity,
                'language': language,
                'address': address,
                'medications': medications,
                'allergies': allergies,
                'diagnostics': diagnostics
            }

            # Handle export options
            if 'export' in request.POST:
                export_type = request.POST['export']
                if export_type == 'json':
                    response = JsonResponse(context)
                    response['Content-Disposition'] = 'attachment; filename="ehr_data.json"'
                    return response
                elif export_type == 'pdf':
                    html = render_to_string('middlewares/result.html', context)
                    result = io.BytesIO()
                    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
                    if not pdf.err:
                        return HttpResponse(result.getvalue(), content_type='application/pdf')
                    return HttpResponse('PDF generation failed', status=500)

            return render(request, 'middlewares/result.html', context)

        except Exception as e:
            return render(request, 'middlewares/result.html', {'error': f"Error parsing XML: {e}"})

    return render(request, 'middlewares/upload.html')
