import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement

ppt_path = r"C:\Users\Hares\Downloads\Software Hackathon PPT Template.pptx"

def set_shape_transparency(shape, transparency_fraction):
    """Sets shape transparency (0.0 = opaque, 1.0 = fully transparent) via raw XML."""
    try:
        spPr = shape._element.spPr
        solidFill = spPr.xpath('a:solidFill')
        if solidFill:
            color_elem = solidFill[0]
            color_clrs = color_elem.xpath('a:srgbClr') or color_elem.xpath('a:schemeClr')
            if color_clrs:
                clr = color_clrs[0]
                # Clear existing alpha tags
                for alpha in clr.xpath('a:alpha'):
                    clr.remove(alpha)
                # Append alpha element
                opacity_val = int((1.0 - transparency_fraction) * 100000)
                alpha = OxmlElement('a:alpha')
                alpha.set('val', str(opacity_val))
                clr.append(alpha)
    except Exception as e:
        print(f"Error setting transparency: {e}")

try:
    prs = Presentation(ppt_path)
    width_in = prs.slide_width / Inches(1)
    height_in = prs.slide_height / Inches(1)
    print(f"Slide Dimensions: Width={width_in:.2f}\", Height={height_in:.2f}\"")
    
    # -------------------------------------------------------------
    # SLIDE 1: Problem and Objectives (Large fonts, wide spread)
    # -------------------------------------------------------------
    slide1 = prs.slides[0]
    
    tb13 = None
    tb14 = None
    for shape in slide1.shapes:
        if shape.name == 'TextBox 13':
            tb13 = shape
        elif shape.name == 'TextBox 14':
            tb14 = shape
            
    if tb13:
        tb13.left = Inches(1.0)
        tb13.top = Inches(6.2)
        tb13.width = Inches(8.5)
        tb13.height = Inches(4.5)
        
        tf = tb13.text_frame
        tf.clear()
        tf.word_wrap = True
        
        # Add Team Name
        p1 = tf.paragraphs[0]
        p1.text = "Team Name: "
        run1 = p1.add_run()
        run1.text = "Data Breakers"
        run1.font.bold = True
        run1.font.color.rgb = RGBColor(59, 130, 246) # Blue accent
        p1.font.size = Pt(24)
        p1.space_after = Pt(8)
        
        # Add Team Leader
        p2 = tf.add_paragraph()
        p2.text = "Team Leader: "
        run2 = p2.add_run()
        run2.text = "Abinav Balasubramaniam"
        run2.font.bold = True
        p2.font.size = Pt(24)
        p2.space_after = Pt(20)
        
        # Add Problem Statement
        p3 = tf.add_paragraph()
        p3.text = "Problem Statement:"
        p3.font.bold = True
        p3.font.size = Pt(22)
        p3.font.color.rgb = RGBColor(255, 255, 255)
        p3.space_after = Pt(8)
        
        p4 = tf.add_paragraph()
        p4.text = "Evaluating candidate resumes manually is highly time-consuming, prone to human cognitive bias, and offers no career up-skilling guides to help students identify and resolve missing required skills."
        p4.font.size = Pt(17)
        p4.font.color.rgb = RGBColor(210, 215, 230)
        
    if tb14:
        # Position tb14 side-by-side on the right half of Slide 1
        tb14.left = Inches(10.5)
        tb14.top = Inches(6.2)
        tb14.width = Inches(8.5)
        tb14.height = Inches(4.5)
        
        tf14 = tb14.text_frame
        tf14.clear()
        tf14.word_wrap = True
        
        p_obj_head = tf14.paragraphs[0]
        p_obj_head.text = "Project Objectives:"
        p_obj_head.font.bold = True
        p_obj_head.font.size = Pt(24)
        p_obj_head.font.color.rgb = RGBColor(139, 92, 246) # Purple accent
        p_obj_head.space_after = Pt(16)
        
        objectives = [
            "Implement an automated, 100% offline, resume parser and scorer using Python and PyPDF.",
            "Provide dual recruiter and student dashboards (Leaderboard vs. Personal Bio Highlights).",
            "Design a career recommendation system matching top companies and providing skills gap roadmaps."
        ]
        
        for obj in objectives:
            p_obj = tf14.add_paragraph()
            p_obj.text = f"• {obj}"
            p_obj.font.size = Pt(17)
            p_obj.space_after = Pt(12)
            p_obj.font.color.rgb = RGBColor(210, 215, 230)

    # -------------------------------------------------------------
    # SLIDE 2: 20-Hour Roadmap (Cleanup overlaps & set XML transparency)
    # -------------------------------------------------------------
    slide2 = prs.slides[1]
    
    # 1. Clean up ALL shapes we added in past runs
    background_shapes = {"Freeform 2", "Freeform 3", "Group 4"}
    shapes_to_remove = []
    for shape in slide2.shapes:
        if shape.name not in background_shapes:
            shapes_to_remove.append(shape)
            
    print(f"Removing {len(shapes_to_remove)} added shapes from Slide 2...")
    for shape in shapes_to_remove:
        sp = shape._element
        sp.getparent().remove(sp)
        
    # 2. Add title text box at the top
    title_box = slide2.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(12.0), Inches(0.8))
    title_box.name = "RoadmapTitle"
    tf_title = title_box.text_frame
    p_title = tf_title.paragraphs[0]
    p_title.text = "20-Hour Development Roadmap"
    p_title.font.bold = True
    p_title.font.size = Pt(36)
    p_title.font.color.rgb = RGBColor(255, 255, 255)
    
    # Roadmap Phase Cards
    phases = [
        {
            "hours": "Hours 0 - 4",
            "title": "Phase 1: Setup & Design",
            "points": [
                "Initialize Git and .gitignore.",
                "Django project & app structures.",
                "Database schema configuration.",
                "Visual CSS design variables."
            ],
            "color": RGBColor(59, 130, 246) # Blue
        },
        {
            "hours": "Hours 4 - 10",
            "title": "Phase 2: Parser & Logic",
            "points": [
                "Implement PDF text extraction.",
                "Write parser regex engines.",
                "Set up tech skills map.",
                "Integrate eligibility rules."
            ],
            "color": RGBColor(6, 182, 212) # Cyan
        },
        {
            "hours": "Hours 10 - 16",
            "title": "Phase 3: Interfaces",
            "points": [
                "Recruiter upload & cockpit.",
                "Student dashboard layouts.",
                "Integrate 50+ job role menus.",
                "Client-side list search filters."
            ],
            "color": RGBColor(139, 92, 246) # Purple
        },
        {
            "hours": "Hours 16 - 20",
            "title": "Phase 4: Integration & QA",
            "points": [
                "Mock email outgoing log outbox.",
                "Verify strict code compilings.",
                "Sync conflicts & push to Git.",
                "System flow check & QA."
            ],
            "color": RGBColor(16, 185, 129) # Green
        }
    ]
    
    col_width = Inches(4.3)
    gap = Inches(0.5)
    top_pos = Inches(3.2)
    
    for idx, phase in enumerate(phases):
        left_pos = Inches(1.0) + idx * (col_width + gap)
        
        # Add shape cards (a rectangle to act as a backing)
        card = slide2.shapes.add_shape(
            1, # Rectangle (MSO_SHAPE.RECTANGLE)
            left_pos, top_pos, col_width, Inches(6.0)
        )
        card.name = f"RoadmapCard_{idx}"
        
        # Style the shape background to be transparent
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(17, 21, 44)
        
        # Apply XML-level transparency (40% transparent / 60% opacity)
        set_shape_transparency(card, 0.40)
            
        card.line.color.rgb = phase["color"]
        card.line.width = Pt(2.5)
        
        # Write text inside the card shape
        tf_card = card.text_frame
        tf_card.word_wrap = True
        tf_card.margin_left = Inches(0.25)
        tf_card.margin_right = Inches(0.25)
        tf_card.margin_top = Inches(0.35)
        tf_card.margin_bottom = Inches(0.3)
        
        # Hours Header
        p_hrs = tf_card.paragraphs[0]
        p_hrs.text = phase["hours"]
        p_hrs.font.bold = True
        p_hrs.font.size = Pt(20)
        p_hrs.font.color.rgb = phase["color"]
        p_hrs.space_after = Pt(4)
        
        # Phase Title
        p_p_title = tf_card.add_paragraph()
        p_p_title.text = phase["title"]
        p_p_title.font.bold = True
        p_p_title.font.size = Pt(17)
        p_p_title.space_after = Pt(14)
        p_p_title.font.color.rgb = RGBColor(255, 255, 255)
        
        # Phase bullet points
        for pt in phase["points"]:
            p_pt = tf_card.add_paragraph()
            p_pt.text = f"• {pt}"
            p_pt.font.size = Pt(13.5)
            p_pt.space_after = Pt(10)
            p_pt.font.color.rgb = RGBColor(200, 210, 225)
            
    # Save the modified presentation
    prs.save(ppt_path)
    print("\nPowerPoint modified and saved successfully!")
    
except Exception as e:
    print(f"Error modifying presentation: {e}")
