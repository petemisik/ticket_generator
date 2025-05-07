from PIL import Image, ImageDraw, ImageFont
import os
import io
import tempfile # Keep for fpdf workaround if still needed by some, though user confirmed fix

try:
    from fpdf import FPDF
except ImportError:
    print("FPDF2 library not found. Please install it: pip install fpdf2")
    print("PDF output will not be available.")
    FPDF = None

DEBUG_ROTATED_TEXT = False

# --- Scaling Factor ---
SCALE_FACTOR = 0.5

# --- Original Configuration (Ticket Design) ---
ORIG_TICKET_WIDTH_PX = 450
ORIG_TICKET_HEIGHT_PX = 200
ORIG_STUB_WIDTH_PX = 100
# ORIG_IMAGE_ON_TICKET_HEIGHT_PX is less relevant now for main image, but kept for scaling consistency
ORIG_IMAGE_ON_TICKET_HEIGHT_PX = 70
ORIG_NUMBER_FONT_SIZE = 24
ORIG_TEXT_FONT_SIZE = 18
ORIG_TICKET_BORDER_WIDTH = 2
ORIG_ROTATED_NUMBER_X_OFFSET_STUB_PX = 15
ORIG_ROTATED_TEXT_PADDING_PX = 5
ORIG_MAIN_BODY_MARGIN_PX = 6 # This will now be padding for text *within* the main body image
ORIG_FRONT_TEXT_TOP_MARGIN_PX = 15
ORIG_FRONT_TEXT_BOTTOM_MARGIN_PX = 15
ORIG_BACK_TEXT_START_Y_PX = 30
ORIG_BACK_TEXT_LINE_SPACING_ADDON_PX = 10
ORIG_BACK_MULTILINE_SPACING_PX = 4
ORIG_BACK_SERIAL_BOTTOM_MARGIN_PX = 30
ORIG_PERFORATION_DASH_STEP_PX = 10
ORIG_PERFORATION_DASH_LENGTH_PX = 5

# --- Scaled Configuration (Ticket Design) ---
TICKET_WIDTH_PX = int(ORIG_TICKET_WIDTH_PX * SCALE_FACTOR)
TICKET_HEIGHT_PX = int(ORIG_TICKET_HEIGHT_PX * SCALE_FACTOR)
STUB_WIDTH_PX = int(ORIG_STUB_WIDTH_PX * SCALE_FACTOR)
IMAGE_ON_TICKET_HEIGHT_PX = int(ORIG_IMAGE_ON_TICKET_HEIGHT_PX * SCALE_FACTOR) # Retained, might be useful for future small overlay logos
NUMBER_FONT_SIZE = max(8, int(ORIG_NUMBER_FONT_SIZE * SCALE_FACTOR))
TEXT_FONT_SIZE = max(6, int(ORIG_TEXT_FONT_SIZE * SCALE_FACTOR))
TICKET_BORDER_WIDTH = max(1, int(ORIG_TICKET_BORDER_WIDTH * SCALE_FACTOR)) if ORIG_TICKET_BORDER_WIDTH > 0 else 0
ROTATED_NUMBER_X_OFFSET_STUB_PX = int(ORIG_ROTATED_NUMBER_X_OFFSET_STUB_PX * SCALE_FACTOR)
ROTATED_TEXT_PADDING_PX = max(2, int(ORIG_ROTATED_TEXT_PADDING_PX * SCALE_FACTOR))
MAIN_BODY_MARGIN_PX = max(3, int(ORIG_MAIN_BODY_MARGIN_PX * SCALE_FACTOR)) # Ensure some padding
FRONT_TEXT_TOP_MARGIN_PX = max(5, int(ORIG_FRONT_TEXT_TOP_MARGIN_PX * SCALE_FACTOR))
FRONT_TEXT_BOTTOM_MARGIN_PX = max(5, int(ORIG_FRONT_TEXT_BOTTOM_MARGIN_PX * SCALE_FACTOR))
BACK_TEXT_START_Y_PX = max(10, int(ORIG_BACK_TEXT_START_Y_PX * SCALE_FACTOR))
BACK_TEXT_LINE_SPACING_ADDON_PX = max(3, int(ORIG_BACK_TEXT_LINE_SPACING_ADDON_PX * SCALE_FACTOR))
BACK_MULTILINE_SPACING_PX = max(1, int(ORIG_BACK_MULTILINE_SPACING_PX * SCALE_FACTOR))
BACK_SERIAL_BOTTOM_MARGIN_PX = max(10, int(ORIG_BACK_SERIAL_BOTTOM_MARGIN_PX * SCALE_FACTOR))
PERFORATION_DASH_STEP_PX = max(4, int(ORIG_PERFORATION_DASH_STEP_PX * SCALE_FACTOR))
PERFORATION_DASH_LENGTH_PX = max(1, int(ORIG_PERFORATION_DASH_LENGTH_PX * SCALE_FACTOR))
if PERFORATION_DASH_LENGTH_PX >= PERFORATION_DASH_STEP_PX :
    PERFORATION_DASH_LENGTH_PX = PERFORATION_DASH_STEP_PX // 2
    PERFORATION_DASH_LENGTH_PX = max(1, PERFORATION_DASH_LENGTH_PX)

# --- Static Configuration (Ticket Design) ---
FONT_PATH = "arial.ttf"
BACKGROUND_COLOR = (255, 255, 255) # Fallback background if image fails, or for ticket back
TICKET_BORDER_COLOR = (150, 150, 150)
ROTATED_NUMBER_ANGLE = -90
EVENT_TITLE = "EVENT TICKET"

# --- Color Configuration ---
TEXT_COLOR_ON_LIGHT_BG = (0, 0, 0)      # Black
TEXT_COLOR_ON_DARK_BG = (255, 255, 255) # White
DEFAULT_STUB_BG_COLOR = (220, 220, 220) # Default light grey for the stub
MAIN_BODY_TEXT_COLOR_OVER_IMAGE = TEXT_COLOR_ON_DARK_BG # Text on main image is white

# --- PDF Sheet Layout Configuration ---
PDF_TICKETS_PER_ROW = 2
PDF_TICKETS_PER_COL = 4
PDF_PAGE_ORIENTATION = 'P'
PDF_PAGE_FORMAT = 'letter'
PDF_MARGIN_PT = 36
PDF_SPACING_PT = 10
EFFECTIVE_DPI_FOR_CONVERSION = 96.0

# --- Helper Functions ---

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        print(f"Error: Font file not found at '{FONT_PATH}'. Using default font.")
        return ImageFont.load_default(size=max(6, int(size * SCALE_FACTOR))) if hasattr(ImageFont, 'load_default') and callable(getattr(ImageFont, 'load_default')) and 'size' in ImageFont.load_default.__code__.co_varnames else ImageFont.load_default()

def get_text_color_for_background(bg_color_tuple):
    """Determines if black or white text is more readable on a given background color."""
    r, g, b = bg_color_tuple
    # Calculate luminance (standard formula)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if luminance > 128:  # Threshold for "light" background
        return TEXT_COLOR_ON_LIGHT_BG  # Black text
    else:
        return TEXT_COLOR_ON_DARK_BG   # White text

def draw_rotated_text(image, text, center_position, font, fill, angle):
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))
    try:
        bbox = dummy_draw.textbbox((0,0), text, font=font)
        text_width_initial = bbox[2] - bbox[0]
        text_height_initial = bbox[3] - bbox[1]
    except AttributeError:
        text_width_initial, text_height_initial = dummy_draw.textsize(text, font=font)

    text_width_initial = max(1, text_width_initial)
    text_height_initial = max(1, text_height_initial)

    padding = ROTATED_TEXT_PADDING_PX
    canvas_width = text_width_initial + 2 * padding
    canvas_height = text_height_initial + 2 * padding
    
    txt_canvas_img = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw_on_canvas = ImageDraw.Draw(txt_canvas_img)
    draw_on_canvas.text((padding, padding), text, font=font, fill=fill)

    actual_content_bbox = txt_canvas_img.getbbox()
    if actual_content_bbox:
        txt_img_cropped = txt_canvas_img.crop(actual_content_bbox)
    else:
        txt_img_cropped = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        
    rotated_txt_img = txt_img_cropped.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    paste_x = center_position[0] - rotated_txt_img.width // 2
    paste_y = center_position[1] - rotated_txt_img.height // 2
    image.paste(rotated_txt_img, (int(paste_x), int(paste_y)), rotated_txt_img)

    if DEBUG_ROTATED_TEXT: # Simplified debug, can be expanded if needed
        print(f"Rotated text '{text}': paste at ({paste_x}, {paste_y}), size {rotated_txt_img.size}")


def create_ticket_front(number_str, image_path, current_stub_bg_color):
    ticket = Image.new("RGB", (TICKET_WIDTH_PX, TICKET_HEIGHT_PX), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(ticket)

    # 1. Define main body area coordinates and dimensions
    # If STUB_WIDTH_PX is 0, main body starts at 0, otherwise it starts after the stub.
    main_body_x_start_coord = STUB_WIDTH_PX if STUB_WIDTH_PX > 0 else 0
    main_body_actual_width = TICKET_WIDTH_PX - main_body_x_start_coord
    main_body_actual_height = TICKET_HEIGHT_PX # Main body covers full ticket height

    # 2. Fill stub background if stub exists
    if STUB_WIDTH_PX > 0:
        # Draw rectangle for stub background slightly smaller if border is thick to avoid peeking
        # Or draw it full and let border overwrite. Let's draw full.
        draw.rectangle(
            [(0, 0), (STUB_WIDTH_PX, TICKET_HEIGHT_PX)], # Covers up to the edge of stub
            fill=current_stub_bg_color
        )

    # 3. Load, resize (crop-to-fill), and paste main body image
    image_loaded_successfully = False
    if image_path and main_body_actual_width > 0 and main_body_actual_height > 0:
        try:
            img_original = Image.open(image_path).convert("RGB") # Convert to RGB

            img_w, img_h = img_original.size
            target_w, target_h = main_body_actual_width, main_body_actual_height
            
            img_aspect = img_w / img_h
            target_aspect = target_w / target_h

            if img_aspect > target_aspect: # Image is wider than target aspect (letterbox top/bottom if not cropping, or crop sides)
                                           # To fill, we resize to match height, then crop width
                new_h = target_h
                new_w = int(new_h * img_aspect)
                img_resized = img_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
                crop_x_offset = (new_w - target_w) // 2
                img_to_paste = img_resized.crop((crop_x_offset, 0, crop_x_offset + target_w, new_h))
            else: # Image is taller or same aspect (pillarbox left/right if not cropping, or crop top/bottom)
                  # To fill, we resize to match width, then crop height
                new_w = target_w
                new_h = int(new_w / img_aspect)
                img_resized = img_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
                crop_y_offset = (new_h - target_h) // 2
                img_to_paste = img_resized.crop((0, crop_y_offset, new_w, crop_y_offset + target_h))
            
            # Ensure final pasted image is exactly target dimensions due to potential rounding
            if img_to_paste.size != (target_w, target_h):
                img_to_paste = img_to_paste.resize((target_w, target_h), Image.Resampling.LANCZOS)

            ticket.paste(img_to_paste, (main_body_x_start_coord, 0))
            image_loaded_successfully = True
        except FileNotFoundError:
            print(f"Warning: Main image '{image_path}' not found. Main body will show fallback BG_COLOR.")
        except Exception as e:
            print(f"Warning: Could not load/resize main image '{image_path}': {e}. Main body will show fallback BG_COLOR.")

    # 4. Determine text color for main body
    # If image loaded, text is MAIN_BODY_TEXT_COLOR_OVER_IMAGE.
    # If not, text color contrasts with BACKGROUND_COLOR.
    current_main_body_text_color = MAIN_BODY_TEXT_COLOR_OVER_IMAGE if image_loaded_successfully else get_text_color_for_background(BACKGROUND_COLOR)

    # 5. Draw text on Main Body (centered in its own content area within main body)
    # Define a content area for text within the main body, with some padding (MAIN_BODY_MARGIN_PX)
    # Text area starts after the stub (if any) plus a margin, and ends before ticket edge minus a margin.
    
    text_area_inner_margin = MAIN_BODY_MARGIN_PX 
    
    # Calculate actual available width for text content placement in main body
    # This handles cases where main_body_actual_width might be too small for margins
    if main_body_actual_width > 2 * text_area_inner_margin:
        text_content_area_x_start = main_body_x_start_coord + text_area_inner_margin
        text_content_area_width = main_body_actual_width - (2 * text_area_inner_margin)
    else: # Not enough space for margins, use full available main_body_width
        text_content_area_x_start = main_body_x_start_coord
        text_content_area_width = main_body_actual_width
        
    # Center point for text within this calculated text_content_area
    if text_content_area_width > 0:
        main_body_text_center_x = text_content_area_x_start + text_content_area_width // 2

        small_font = load_font(TEXT_FONT_SIZE)
        event_text_y = FRONT_TEXT_TOP_MARGIN_PX # Margin from top of ticket
        try:
            draw.text((main_body_text_center_x, event_text_y), EVENT_TITLE, font=small_font, fill=current_main_body_text_color, anchor="mt")
        except TypeError: # Fallback for older Pillow
            et_w, _ = draw.textsize(EVENT_TITLE, font=small_font)
            draw.text((main_body_text_center_x - et_w // 2, event_text_y), EVENT_TITLE, font=small_font, fill=current_main_body_text_color)

        num_text_y = TICKET_HEIGHT_PX - FRONT_TEXT_BOTTOM_MARGIN_PX # Margin from bottom
        try:
            # Draw a small box around the text, fill it white, and set the text color to contrast with the box
            # Get the text size to generate the box
            bbox_num = draw.textbbox((main_body_text_center_x, num_text_y), f"No. {number_str}", font=small_font, anchor="mb")
            num_text_width = bbox_num[2] - bbox_num[0]
            num_text_height = bbox_num[3] - bbox_num[1]
            # Draw a rectangle around the text
            # Adjust the rectangle size to fit the text
            # Draw the rectangle with a small padding
            # draw.rectangle([(main_body_text_center_x - 20, num_text_y - 10), (main_body_text_center_x + 20, num_text_y + 10)], fill=(255, 255, 255))
            draw.rectangle([(bbox_num[0] - 2, bbox_num[1] - 2), (bbox_num[2] + 2, bbox_num[3] + 2)], fill=(255, 255, 255))
            draw.text((main_body_text_center_x, num_text_y), f"No. {number_str}", font=small_font, fill=(0,0,0), anchor="mb")
        except TypeError:
            ns_w, ns_h = draw.textsize(f"No. {number_str}", font=small_font)
            draw.text((main_body_text_center_x - ns_w // 2, num_text_y - ns_h), f"No. {number_str}", font=small_font, fill=current_main_body_text_color)

    # 6. Draw Rotated Number on Stub
    if STUB_WIDTH_PX > 0:
        number_font = load_font(NUMBER_FONT_SIZE)
        # Determine text color for stub number based on stub_bg_color
        stub_number_text_color = get_text_color_for_background(current_stub_bg_color)
        
        base_stub_center_x = STUB_WIDTH_PX // 2
        final_stub_center_x = base_stub_center_x + ROTATED_NUMBER_X_OFFSET_STUB_PX
        stub_center_y = TICKET_HEIGHT_PX // 2
        draw_rotated_text(ticket, number_str, (final_stub_center_x, stub_center_y),
                          number_font, stub_number_text_color, ROTATED_NUMBER_ANGLE)

    # 7. Draw Border and Perforation Line (on top of everything else)
    if TICKET_BORDER_WIDTH > 0:
        draw.rectangle(
            [(0,0), (TICKET_WIDTH_PX - 1, TICKET_HEIGHT_PX - 1)], # Draw border within ticket dimensions
            outline=TICKET_BORDER_COLOR,
            width=TICKET_BORDER_WIDTH
        )
        # Perforation line is drawn at the edge of the stub
        if STUB_WIDTH_PX > 0 and STUB_WIDTH_PX < TICKET_WIDTH_PX:
            line_x = STUB_WIDTH_PX 
            # Adjust perforation start/end to be inside the main border (if border is thick)
            # Or simply draw it from edge to edge of height if border effect is desired over it.
            # For simplicity, let's assume width 1 perforation for now, drawn from border to border.
            y_start_perf = TICKET_BORDER_WIDTH 
            y_end_perf = TICKET_HEIGHT_PX - TICKET_BORDER_WIDTH
            
            for y_dash in range(y_start_perf, y_end_perf, PERFORATION_DASH_STEP_PX):
                dash_end_y = min(y_dash + PERFORATION_DASH_LENGTH_PX, y_end_perf)
                if dash_end_y > y_dash: # Only draw if there's positive length
                    draw.line([(line_x, y_dash), (line_x, dash_end_y)], fill=TICKET_BORDER_COLOR, width=1) # Width 1 for perforation
    return ticket

def create_ticket_back(number_str):
    # (This function remains unchanged from the previous version,
    # but ensure text colors contrast with BACKGROUND_COLOR if it's changed)
    ticket = Image.new("RGB", (TICKET_WIDTH_PX, TICKET_HEIGHT_PX), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(ticket)

    if TICKET_BORDER_WIDTH > 0:
        draw.rectangle(
            [(0,0), (TICKET_WIDTH_PX - 1, TICKET_HEIGHT_PX - 1)],
            outline=TICKET_BORDER_COLOR,
            width=TICKET_BORDER_WIDTH
        )

    text_font = load_font(TEXT_FONT_SIZE)
    current_y = BACK_TEXT_START_Y_PX
    text_y_spacing = TEXT_FONT_SIZE + BACK_TEXT_LINE_SPACING_ADDON_PX
    
    # Determine text color for back based on general BACKGROUND_COLOR
    back_text_color = get_text_color_for_background(BACKGROUND_COLOR)

    try:
        draw.text((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, fill=back_text_color, anchor="mt")
        bbox_tb = draw.textbbox((TICKET_WIDTH_PX // 2, current_y), "TICKET BACK", font=text_font, anchor="mt")
        current_y += (bbox_tb[3] - bbox_tb[1]) + text_y_spacing // 2
    except TypeError:
        tb_w, tb_h = draw.textsize("TICKET BACK", font=text_font)
        draw.text(((TICKET_WIDTH_PX - tb_w) // 2, current_y), "TICKET BACK", font=text_font, fill=back_text_color)
        current_y += tb_h + text_y_spacing // 2

    terms_text = "Terms and Conditions Apply.\nVisit website for details."
    try:
        bbox_terms = draw.multiline_textbbox((0, 0), terms_text, font=text_font, spacing=BACK_MULTILINE_SPACING_PX, align="center")
        multiline_width = bbox_terms[2] - bbox_terms[0]
        multiline_height = bbox_terms[3] - bbox_terms[1]
    except AttributeError:
        lines = terms_text.splitlines()
        max_w = 0; total_h = 0
        for i, line in enumerate(lines):
            lw, lh = draw.textsize(line, font=text_font)
            if lw > max_w: max_w = lw
            total_h += lh
            if i < len(lines) -1: total_h += BACK_MULTILINE_SPACING_PX
        multiline_width = max_w; multiline_height = total_h

    x_terms = (TICKET_WIDTH_PX - multiline_width) // 2
    draw.multiline_text((x_terms, current_y), terms_text, font=text_font, fill=back_text_color, align="center", spacing=BACK_MULTILINE_SPACING_PX)

    serial_y_pos_from_bottom = TICKET_HEIGHT_PX - BACK_SERIAL_BOTTOM_MARGIN_PX
    try:
        draw.text((TICKET_WIDTH_PX // 2, serial_y_pos_from_bottom), f"Serial: {number_str}", font=text_font, fill=back_text_color, anchor="mb")
    except TypeError:
        sn_w, sn_h = draw.textsize(f"Serial: {number_str}", font=text_font)
        draw.text(((TICKET_WIDTH_PX - sn_w) // 2, serial_y_pos_from_bottom - sn_h), f"Serial: {number_str}", font=text_font, fill=back_text_color)
    
    return ticket

# --- PDF Generation Function (generate_pdf_from_images - unchanged from previous) ---
def generate_pdf_from_images(ticket_pil_images, output_filename="ticket_sheet.pdf"):
    if FPDF is None:
        print("FPDF library not available. Cannot generate PDF.")
        return

    ticket_width_pt = TICKET_WIDTH_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION
    ticket_height_pt = TICKET_HEIGHT_PX * 72.0 / EFFECTIVE_DPI_FOR_CONVERSION

    pdf = FPDF(orientation=PDF_PAGE_ORIENTATION, unit='pt', format=PDF_PAGE_FORMAT)
    pdf.set_auto_page_break(False)

    tickets_per_page = PDF_TICKETS_PER_ROW * PDF_TICKETS_PER_COL
    ticket_index_on_page = 0

    for i, pil_image in enumerate(ticket_pil_images):
        if ticket_index_on_page == 0:
            pdf.add_page()
            if i == 0: # Check only for the first page setup
                page_content_width_pt = pdf.w - 2 * PDF_MARGIN_PT
                page_content_height_pt = pdf.h - 2 * PDF_MARGIN_PT
                required_width_for_tickets_pt = (PDF_TICKETS_PER_ROW * ticket_width_pt) + \
                                                ((PDF_TICKETS_PER_ROW - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_ROW > 1 else 0)
                required_height_for_tickets_pt = (PDF_TICKETS_PER_COL * ticket_height_pt) + \
                                                 ((PDF_TICKETS_PER_COL - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_COL > 1 else 0)
                if required_width_for_tickets_pt > page_content_width_pt:
                    print(f"Warning: Ticket block width ({required_width_for_tickets_pt:.2f}pt) exceeds PDF content width ({page_content_width_pt:.2f}pt).")
                if required_height_for_tickets_pt > page_content_height_pt:
                    print(f"Warning: Ticket block height ({required_height_for_tickets_pt:.2f}pt) exceeds PDF content height ({page_content_height_pt:.2f}pt).")

        col_num = ticket_index_on_page % PDF_TICKETS_PER_ROW
        row_num = ticket_index_on_page // PDF_TICKETS_PER_ROW
        
        page_content_width_pt = pdf.w - 2 * PDF_MARGIN_PT
        total_width_of_row_pt = (PDF_TICKETS_PER_ROW * ticket_width_pt) + \
                                ((PDF_TICKETS_PER_ROW - 1) * PDF_SPACING_PT if PDF_TICKETS_PER_ROW > 1 else 0)
        x_offset_for_centering_pt = (page_content_width_pt - total_width_of_row_pt) / 2
        
        x_pt = PDF_MARGIN_PT + x_offset_for_centering_pt + col_num * (ticket_width_pt + PDF_SPACING_PT)
        y_pt = PDF_MARGIN_PT + row_num * (ticket_height_pt + PDF_SPACING_PT)

        # Using BytesIO is generally preferred and should work with up-to-date fpdf2
        with io.BytesIO() as img_byte_stream:
            pil_image.save(img_byte_stream, format="PNG")
            img_byte_stream.seek(0)
            pdf.image(img_byte_stream, x=x_pt, y=y_pt, w=ticket_width_pt, h=ticket_height_pt, type="PNG")

        ticket_index_on_page += 1
        if ticket_index_on_page >= tickets_per_page:
            ticket_index_on_page = 0

    pdf.output(output_filename, "F")
    print(f"Saved PDF: {output_filename}")


# --- Main Execution ---
if __name__ == "__main__":
    start_number = int(input("Enter starting ticket number: "))
    end_number = int(input("Enter ending ticket number: "))
    image_file_path = input("Enter path to the image for the ticket main body background: ")
    num_leading_zeros = int(input("Enter number of leading zeros for ticket numbers (e.g., 5 for 00001): "))
    event_title = input("Enter event title (default is 'EVENT TICKET'): ")
    if event_title.strip():
        EVENT_TITLE = event_title.strip()

    # Get stub background color from user
    stub_color_input_str = input(f"Enter stub background color (R,G,B like '255,0,128') or press Enter for default ({DEFAULT_STUB_BG_COLOR}): ")
    if stub_color_input_str.strip():
        try:
            # Parse R,G,B values
            r, g, b = map(int, stub_color_input_str.split(','))
            if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                raise ValueError("RGB values must be between 0 and 255.")
            STUB_BACKGROUND_COLOR_USER = (r, g, b)
        except ValueError as e:
            print(f"Invalid color input: {e}. Using default stub color {DEFAULT_STUB_BG_COLOR}.")
            STUB_BACKGROUND_COLOR_USER = DEFAULT_STUB_BG_COLOR
    else:
        STUB_BACKGROUND_COLOR_USER = DEFAULT_STUB_BG_COLOR
    print(f"Using stub background color: {STUB_BACKGROUND_COLOR_USER}")


    if not (os.path.exists(image_file_path) or image_file_path.strip() == ""):
        print(f"Error: Image file '{image_file_path}' not found. Exiting.")
        exit()
    if image_file_path.strip() == "":
        print("No image path provided. Main body of tickets will use fallback background color.")
        image_file_path = None

    if FPDF is None:
        print("FPDF2 library is not installed. PDF output is disabled. Exiting.")
        exit()
    
    if start_number > end_number:
        print("Error: Start number cannot be greater than end number. Exiting.")
        exit()

    all_front_pil_images = []
    all_back_pil_images = []

    print("\nGenerating ticket images (using Pillow)...")
    print(f"Target ticket size (WxH): {TICKET_WIDTH_PX}px x {TICKET_HEIGHT_PX}px")
    if image_file_path:
        print(f"Main body image: '{image_file_path}' will be used as background.")
    
    total_tickets = end_number - start_number + 1
    for count, i in enumerate(range(start_number, end_number + 1)):
        number_string = str(i).zfill(num_leading_zeros)
        if (count + 1) % 10 == 0 or (count + 1) == 1 or (count + 1) == total_tickets :
             print(f"  Creating ticket No. {number_string} ({(count + 1)} of {total_tickets})")

        # Pass the user-defined or default stub background color
        front_pil = create_ticket_front(number_string, image_file_path, STUB_BACKGROUND_COLOR_USER)
        all_front_pil_images.append(front_pil)

        back_pil = create_ticket_back(number_string)
        all_back_pil_images.append(back_pil)

    print(f"\nGenerated {len(all_front_pil_images)} ticket images with Pillow.")

    if FPDF is not None:
        print("\nGenerating PDF files...")
        if all_front_pil_images:
            generate_pdf_from_images(all_front_pil_images, "ticket_sheet_fronts.pdf")
            generate_pdf_from_images(all_back_pil_images, "ticket_sheet_backs.pdf")
            print("\nPDF generation complete.")
        else:
            print("No ticket images were generated, so no PDF will be created.")
    else:
        print("Skipping PDF generation as FPDF2 is not installed or failed to import.")

    print("\nDone!")