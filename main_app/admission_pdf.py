import os
from html import escape
from io import BytesIO
from threading import Lock
from uuid import uuid4

from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_font_registration_lock = Lock()
_english_font_name = 'Times-Roman'


def admission_pdf_download_filename(application):
    application_data = application.application_data or {}
    student_name = (
        application_data.get('student_name_en')
        or application_data.get('student_name_bn')
        or f'application-{application.pk}'
    )
    safe_student_name = slugify(student_name, allow_unicode=True) or f'application-{application.pk}'
    class_number = next(
        (
            index
            for index, (class_name, _) in enumerate(
                application.ADMISSION_CLASS_CHOICES,
                start=6,
            )
            if class_name == application.admission_class
        ),
        None,
    )
    safe_class = f'class-{class_number}' if class_number else (
        slugify(application.admission_class, allow_unicode=True) or 'class'
    )
    return f'{safe_student_name}-{safe_class}-{application.academic_year}.pdf'


def _register_kalpurush_font():
    global _english_font_name
    with _font_registration_lock:
        if 'Kalpurush' not in pdfmetrics.getRegisteredFontNames():
            font_path = finders.find('fonts/Kalpurush-v0.258.ttf')
            if not font_path:
                raise FileNotFoundError('Kalpurush font file was not found in static files.')
            pdfmetrics.registerFont(TTFont('Kalpurush', font_path))
        pdfmetrics.registerFontFamily(
            'Kalpurush',
            normal='Kalpurush',
            bold='Kalpurush',
            italic='Kalpurush',
            boldItalic='Kalpurush',
        )
        windows_dir = os.environ.get('WINDIR', r'C:\Windows')
        english_font_path = os.path.join(windows_dir, 'Fonts', 'times.ttf')
        if os.path.isfile(english_font_path):
            if 'TimesNewRoman' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('TimesNewRoman', english_font_path))
            pdfmetrics.registerFontFamily(
                'TimesNewRoman',
                normal='TimesNewRoman',
                bold='TimesNewRoman',
                italic='TimesNewRoman',
                boldItalic='TimesNewRoman',
            )
            _english_font_name = 'TimesNewRoman'


def _paragraph(value, style):
    text = str(value or '-')
    selected_style = style
    if (
        not any('\u0980' <= character <= '\u09ff' for character in text)
        and getattr(style, 'fontName', '') == 'Kalpurush'
    ):
        selected_style = style.clone(
            f'{style.name}English',
            fontName=_english_font_name,
            shaping=False,
        )
    escaped = escape(text).replace('\n', '<br/>')
    return Paragraph(escaped, selected_style)


def generate_admission_pdf(application):
    _register_kalpurush_font()
    school_data = {
        'school_name_bangla': 'খন্দকার নাসের উদ্দীন মাধ্যমিক বিদ্যালয়',
        'school_name_english': 'Khondoker Naser Uddin High School',
        'school_code': '৩৫৭৪',
        'eiin': '117407',
    }
    data = {
        **school_data,
        **application.application_data,
        'application_id': application.application_id,
        'class_roll_number': f'{application.class_roll_number:02d}' if application.class_roll_number else '-',
        'assigned_section': application.get_assigned_section_display() or '-',
    }
    attached_documents = data.get('attached_documents', [])
    if isinstance(attached_documents, str):
        attached_documents = [
            item.strip() for item in attached_documents.split(',') if item.strip()
        ]

    normal = ParagraphStyle(
        'AdmissionNormal',
        fontName='Kalpurush',
        fontSize=9,
        leading=14,
        textColor=colors.HexColor('#172638'),
        shaping=True,
    )
    label = ParagraphStyle(
        'AdmissionLabel',
        parent=normal,
        fontName='Kalpurush',
        textColor=colors.HexColor('#103d75'),
    )
    heading = ParagraphStyle(
        'AdmissionSection',
        parent=normal,
        fontSize=11,
        leading=16,
        textColor=colors.white,
        borderPadding=5,
        shaping=True,
    )
    school_title = ParagraphStyle(
        'AdmissionSchoolTitle',
        parent=normal,
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#103d75'),
    )
    school_english = ParagraphStyle(
        'AdmissionSchoolEnglish',
        parent=normal,
        fontName=_english_font_name,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        shaping=True,
    )
    english_field = ParagraphStyle(
        'AdmissionEnglishField',
        parent=school_english,
        alignment=TA_LEFT,
    )
    school_address = ParagraphStyle(
        'AdmissionSchoolAddress',
        parent=normal,
        alignment=TA_CENTER,
    )
    school_english_address = ParagraphStyle(
        'AdmissionSchoolEnglishAddress',
        parent=school_english,
        alignment=TA_CENTER,
    )
    footer_style = ParagraphStyle(
        'AdmissionFooter',
        parent=normal,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#103d75'),
        shaping=True,
    )
    title = ParagraphStyle(
        'AdmissionTitle',
        parent=school_title,
        fontSize=13,
        leading=18,
    )

    width, _ = A4
    content_width = width - 32 * mm
    label_width = 48 * mm

    def table_for(rows, widths=None):
        table = Table(
            [
                [
                    _paragraph(name, label),
                    value if isinstance(value, Paragraph) else _paragraph(value, normal),
                ]
                for name, value in rows
            ],
            colWidths=widths or [label_width, content_width - label_width],
            repeatRows=0,
            hAlign='LEFT',
        )
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eaf2fc')),
            ('ROWBACKGROUNDS', (1, 0), (-1, -1), [
                colors.white,
                colors.HexColor('#f6faff'),
            ]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        return table

    sections = [
        ('১. শিক্ষার্থীর ব্যক্তিগত তথ্য', [
            ('লিঙ্গ / ধর্ম / রক্তের গ্রুপ', ' / '.join(
                data.get(key, '') or '-' for key in ('gender', 'religion', 'blood_group')
            )),
            ('জাতীয়তা', data.get('nationality')),
            ('বিশেষ শিক্ষাসহায়তার তথ্য', data.get('special_support_info')),
        ]),
        ('২. ভর্তি-সংক্রান্ত তথ্য', [
            ('শ্রেণি / শিক্ষাবর্ষ', f"{data.get('admission_class') or '-'} / {data.get('academic_year') or '-'}"),
            ('শাখা / আবেদন রোল / গ্রুপ / শিফট', ' / '.join(
                (data.get('assigned_section') or '-', data.get('class_roll_number') or '-')
                + tuple(data.get(key, '') or '-' for key in ('group', 'shift'))
            )),
            ('ভর্তির তারিখ / ধরন', f"{data.get('admission_date') or '-'} / {data.get('admission_type') or '-'}"),
        ]),
        ('৩. পিতা-মাতা ও অভিভাবকের তথ্য', [
            ('পিতার পূর্ণ নাম (বাংলা)', data.get('father_name_bn') or data.get('father_name')),
            ('পিতার পূর্ণ নাম (ইংরেজি)', _paragraph(data.get('father_name_en'), english_field)),
            ('পিতার পেশা / মোবাইল', ' / '.join(
                data.get(key, '') or '-' for key in ('father_occupation', 'father_mobile')
            )),
            ('মাতার পূর্ণ নাম (বাংলা)', data.get('mother_name_bn') or data.get('mother_name')),
            ('মাতার পূর্ণ নাম (ইংরেজি)', _paragraph(data.get('mother_name_en'), english_field)),
            ('মাতার পেশা / মোবাইল', ' / '.join(
                data.get(key, '') or '-' for key in ('mother_occupation', 'mother_mobile')
            )),
            ('অভিভাবকের নাম / সম্পর্ক / মোবাইল', ' / '.join(
                data.get(key, '') or '-' for key in ('guardian_name', 'guardian_relation', 'guardian_mobile')
            )),
            ('পিতা-মাতার NID / জরুরি যোগাযোগ', f"{data.get('parent_nid') or '-'} / {data.get('emergency_contact') or '-'}"),
        ]),
        ('৪. ঠিকানা', [
            ('বর্তমান ঠিকানা', data.get('present_address')),
            ('স্থায়ী ঠিকানা', data.get('permanent_address')),
            ('গ্রাম/মহল্লা / ডাকঘর / উপজেলা / জেলা / পোস্টকোড', ' / '.join(
                data.get(key, '') or '-'
                for key in ('village', 'post_office', 'upazila', 'district', 'postcode')
            )),
            ('বর্তমান ও স্থায়ী ঠিকানা একই', data.get('same_as_permanent')),
        ]),
        ('৫. পূর্ববর্তী শিক্ষাপ্রতিষ্ঠানের তথ্য', [
            ('পূর্ববর্তী স্কুল / ঠিকানা', f"{data.get('previous_school_name') or '-'} / {data.get('previous_school_address') or '-'}"),
            ('সর্বশেষ শ্রেণি / ফলাফল / রোল', ' / '.join(
                data.get(key, '') or '-'
                for key in ('last_study_class', 'last_exam_result', 'previous_roll')
            )),
            ('বোর্ড পরীক্ষার তথ্য', data.get('board_exam_info')),
            ('TC সংযুক্তির বিবরণ', data.get('tc_reference')),
        ]),
        ('৬. প্রয়োজনীয় কাগজপত্র', [
            (
                'আবেদনকারীর নির্বাচিত কাগজপত্র',
                '\n'.join(f'[x] {item}' for item in attached_documents)
                or 'কোনো কাগজপত্রের পাশে টিক দেওয়া হয়নি।',
            ),
        ]),
        ('৭. আবেদন ফি ও পেমেন্ট', [
            ('আবেদন ফি', f"৳ {data.get('application_fee', '0.00')}"),
            ('পেমেন্টের মাধ্যম', data.get('payment_method_display')),
            ('Transaction ID / রেফারেন্স', data.get('payment_reference')),
            ('পেমেন্টের অবস্থা', application.get_payment_status_display()),
            ('আবেদনকারীর ইমেইল', _paragraph(data.get('email'), english_field)),
        ]),
        ('৮. স্কুল অফিসের ব্যবহারের জন্য', [
            ('Admission ID / আবেদনের অবস্থা / পেমেন্ট', ' / '.join((
                application.application_id or '-',
                application.get_status_display(),
                application.get_payment_status_display(),
            ))),
            ('নির্ধারিত শ্রেণি / শাখা / রোল', ' / '.join((
                application.get_assigned_class_display() or '-',
                application.get_assigned_section_display() or '-',
                f'{application.assigned_roll:02d}' if application.assigned_roll else '-',
            ))),
            ('অনুমোদনকারীর নাম / ভর্তি নিশ্চিতের তারিখ', ' / '.join((
                application.approver_name or '-',
                application.admission_confirmed_at.strftime('%d-%m-%Y') if application.admission_confirmed_at else '-',
            ))),
            ('মন্তব্য', application.office_comment),
        ]),
    ]

    school_logo_path = finders.find('images/logo.png')
    school_logo = (
        Image(school_logo_path, width=20 * mm, height=20 * mm, kind='proportional')
        if school_logo_path else ''
    )
    school_details = Table(
        [
            [_paragraph(data['school_name_bangla'], school_title)],
            [_paragraph(data['school_name_english'], school_english)],
            [_paragraph('হাজী ফয়েজ উদ্দীন ক্রস রোড', school_address)],
            [_paragraph('পোস্টঃ জিপিও-৯০০০, থানাঃ সোনাডাঙ্গা, জেলাঃ খুলনা', school_address)],
            [_paragraph('মোবাঃ ০১৩০৯১১৭৪০৭, ০১৭১৪৯৩৯১২২', school_address)],
            [_paragraph(f"বিদ্যালয় কোডঃ {data['school_code']}", school_address)],
            [_paragraph(f"EIIN: {escape(data['eiin'])}", school_english_address)],
        ],
        colWidths=[content_width - (48 * mm if school_logo_path else 0)],
        hAlign='CENTER',
    )
    school_header = Table(
        [[school_logo, school_details, '']] if school_logo_path else [[school_details]],
        colWidths=[24 * mm, content_width - 48 * mm, 24 * mm] if school_logo_path else [content_width],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f8ff')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#c5d9ef')),
            ('LINEBELOW', (0, 0), (-1, -1), 3, colors.HexColor('#d6a32a')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]),
    )

    story = [
        school_header,
        Spacer(1, 5 * mm),
        _paragraph(
            f"ভর্তি আবেদন ফরম — Application ID: {application.application_id or '-'}"
            f" — শ্রেণিভিত্তিক রোল: {application.class_roll_number:02d}" if application.class_roll_number
            else f"ভর্তি আবেদন ফরম — Application ID: {application.application_id or '-'}",
            title,
        ),
        Spacer(1, 3 * mm),
    ]
    if application.student_photo and application.student_photo.storage.exists(application.student_photo.name):
        with application.student_photo.open('rb') as photo_file:
            photo_bytes = photo_file.read()
        photo = Image(BytesIO(photo_bytes), width=25 * mm, height=30 * mm)
    else:
        photo = _paragraph('ছবি পাওয়া যায়নি', normal)
    student_rows = [
        [_paragraph('আবেদনের তারিখ', label), _paragraph(application.submitted_at.strftime('%d-%m-%Y %H:%M'), normal), '', photo],
        [_paragraph('শিক্ষার্থীর পূর্ণ নাম (বাংলা)', label), _paragraph(data.get('student_name_bn'), normal), '', ''],
        [_paragraph('শিক্ষার্থীর নাম (ইংরেজি)', label), _paragraph(data.get('student_name_en'), english_field), '', ''],
        [_paragraph('জন্মতারিখ / জন্মনিবন্ধন নম্বর', label), _paragraph(
            f"{data.get('date_of_birth') or '-'} / {data.get('birth_reg_no') or '-'}", normal
        ), '', ''],
    ]
    student_table = Table(
        student_rows,
        colWidths=[label_width, content_width - label_width - 25 * mm, 0, 25 * mm],
        hAlign='LEFT',
    )
    student_table.setStyle(TableStyle([
        ('SPAN', (1, 0), (2, 0)),
        ('SPAN', (1, 1), (2, 1)),
        ('SPAN', (1, 2), (2, 2)),
        ('SPAN', (1, 3), (2, 3)),
        ('SPAN', (3, 0), (3, 3)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eaf2fc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (3, 0), (3, 3), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(student_table)

    for section_title, rows in sections:
        story.extend([
            Spacer(1, 3 * mm),
            Table(
                [[_paragraph(section_title, heading)]],
                colWidths=[content_width],
                style=TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#176fb7')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#123f70')),
                    ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#d6a32a')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 7),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]),
            ),
            table_for(rows),
        ])

    signature_table = Table(
        [[_paragraph('প্রধান শিক্ষকের স্বাক্ষর', normal)]],
        colWidths=[58 * mm],
        hAlign='RIGHT',
        style=TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.HexColor('#52657a')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]),
    )
    story.extend([Spacer(1, 10 * mm), signature_table])

    output = BytesIO()
    def draw_page_number(canvas, document):
        canvas.saveState()
        footer = Paragraph('শিক্ষাই জাতির মেরুদন্ড', footer_style)
        footer_width, _ = footer.wrapOn(canvas, content_width, 14 * mm)
        footer.drawOn(canvas, (width - footer_width) / 2, 3 * mm)
        canvas.setFont(_english_font_name, 8)
        canvas.setFillColor(colors.HexColor('#65758b'))
        canvas.drawRightString(width - 16 * mm, 7 * mm, f'Page {document.page}')
        canvas.restoreState()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Admission Application {application.pk}",
    )
    document.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
    application.pdf_file.save(
        f'admission-application-v9-{uuid4().hex}.pdf',
        ContentFile(output.getvalue()),
        save=True,
    )


def ensure_admission_pdf(application):
    current_pdf = (
        application.pdf_file
        and application.pdf_file.name.rsplit('/', 1)[-1].startswith('admission-application-v9-')
        and application.pdf_file.storage.exists(application.pdf_file.name)
    )
    if not current_pdf:
        generate_admission_pdf(application)

    if not application.pdf_file or not application.pdf_file.storage.exists(application.pdf_file.name):
        raise FileNotFoundError(f'Could not generate PDF for admission application {application.pk}.')
