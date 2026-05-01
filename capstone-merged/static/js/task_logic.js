let isNavigating = false;

// empty answers for optional questions
const form = document.getElementById('survey-form');
if (form) { 
    form.addEventListener('submit', () => {
        isNavigating = true;
        let ans = document.getElementById('answer_data').value;
        if (!ans || ans === '{}' || ans === '""' || ans === '{"choices":[]}') {
            document.getElementById('answer_data').value = '"empty"'; 
        }
    }); 
}

document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => isNavigating = true);
});

window.addEventListener('beforeunload', function (e) {
    if (!isNavigating) {
        e.preventDefault();
        e.returnValue = 'Are you sure you want to close the survey? Your current progress is saved.';
    }
});

document.addEventListener("DOMContentLoaded", () => {
    if (typeof IS_OPTIONAL !== 'undefined' && IS_OPTIONAL) {
        const nextBtn = document.getElementById('next-button');
        if (nextBtn) nextBtn.disabled = false;
    }
});

function setupSpatialTask(currentQ, savedAnswerRaw) {
    const objectsList = ["car", "stop sign", "traffic light", "cat", "house", "tree", "flower"];
    
    if (currentQ === 0) {
        document.getElementById('lbl-facing').innerText = "Tree";
        document.getElementById('lbl-standing').innerText = "Flower";
        document.getElementById('prompt-standing').innerText = "flower";
        document.getElementById('prompt-facing').innerText = "tree";
        document.getElementById('prompt-pointing').innerText = "cat";
    } else {
        const shuffled = [...objectsList].sort(() => 0.5 - Math.random());
        const facingObj = shuffled[0];
        const standingObj = shuffled[1];
        const pointingObj = shuffled[2];
        
        const capitalize = (s) => s.replace(/\b\w/g, l => l.toUpperCase());

        document.getElementById('lbl-facing').innerText = capitalize(facingObj);
        document.getElementById('lbl-standing').innerText = capitalize(standingObj);
        document.getElementById('prompt-facing').innerText = facingObj;
        document.getElementById('prompt-standing').innerText = standingObj;
        document.getElementById('prompt-pointing').innerText = pointingObj;

        document.getElementById('facing_obj').value = capitalize(facingObj);
        document.getElementById('standing_obj').value = capitalize(standingObj);
    }

    const canvas = document.getElementById('task-canvas');
    const ctx = canvas.getContext('2d');
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    let interactiveArrowEndPoint = null; 

    function drawArrow(toX, toY, color) {
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(toX, toY);
        ctx.strokeStyle = color; 
        ctx.lineWidth = 3;
        ctx.stroke();
        const angle = Math.atan2(toY - centerY, toX - centerX);
        const headLength = 15;
        ctx.beginPath();
        ctx.moveTo(toX, toY);
        ctx.lineTo(toX - headLength * Math.cos(angle - Math.PI / 6), toY - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(toX - headLength * Math.cos(angle + Math.PI / 6), toY - headLength * Math.sin(angle + Math.PI / 6));
        ctx.lineTo(toX, toY);
        ctx.fillStyle = color;
        ctx.fill();
    }

    function drawFixedElements() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawArrow(centerX, centerY - 123, '#999'); 
    }

    function updateCanvas() {
        drawFixedElements();
        if (interactiveArrowEndPoint) {
            drawArrow(interactiveArrowEndPoint.x, interactiveArrowEndPoint.y, '#c59b48');
        }
    }

    if (savedAnswerRaw && savedAnswerRaw.x !== undefined && savedAnswerRaw.y !== undefined) {
        interactiveArrowEndPoint = { x: savedAnswerRaw.x, y: savedAnswerRaw.y };
        document.getElementById('answer_data').value = JSON.stringify(savedAnswerRaw);
        document.getElementById('next-button').disabled = false;
    }

    updateCanvas();

    canvas.addEventListener('click', function(event) {
        const rect = canvas.getBoundingClientRect();
        let clickX = event.clientX - rect.left;
        let clickY = event.clientY - rect.top;
        
        let dx = clickX - centerX;
        let dy = clickY - centerY; 
        
        let clickAngle = Math.atan2(dy, dx);
        let radius = 123; 
        
        interactiveArrowEndPoint = {
            x: Math.round(centerX + radius * Math.cos(clickAngle)),
            y: Math.round(centerY + radius * Math.sin(clickAngle))
        };
        
        let px = -1 * dx;
        let py = dy;
        
        let angleRad = Math.atan2(px, py);
        let angleDeg = Math.round((angleRad * (180 / Math.PI)) + 180) % 360;
        
        if (angleDeg > 180) {
            angleDeg = 360 - angleDeg;
        }
        
        let correctAngle = typeof CORRECT_ANGLE !== 'undefined' ? CORRECT_ANGLE : 45; 
        let angleOfDeviance = Math.abs(angleDeg - correctAngle);
        
        updateCanvas();
        
        document.getElementById('answer_data').value = JSON.stringify({ 
            x: interactiveArrowEndPoint.x, 
            y: interactiveArrowEndPoint.y, 
            angle: angleDeg,
            correct_angle: correctAngle,
            angle_of_deviance: angleOfDeviance,
            timestamp: Date.now() 
        });
        
        document.getElementById('next-button').disabled = false;
    });
}

let currentSlide = 1;
const totalSlides = 4;
function changeSlide(direction) {
    document.getElementById(`slide-${currentSlide}`).classList.remove('active');
    currentSlide += direction;
    document.getElementById(`slide-${currentSlide}`).classList.add('active');
    
    document.getElementById('btn-prev').disabled = currentSlide === 1;
    
    if (currentSlide === totalSlides) {
        document.getElementById('btn-next-slide').style.display = 'none';
        document.getElementById('btn-submit-sample').style.display = 'inline-block';
    } else {
        document.getElementById('btn-next-slide').style.display = 'inline-block';
        document.getElementById('btn-submit-sample').style.display = 'none';
    }
}

const selectedMR = new Set();
function setupMRTask(savedMR) {
    if (savedMR && Array.isArray(savedMR.choices)) {
        savedMR.choices.forEach(id => {
            selectedMR.add(id);
            document.getElementById('mr-box-' + id).classList.add('selected');
            document.getElementById('mr-chk-' + id).checked = true;
        });
        if (selectedMR.size > 0) {
            document.getElementById('next-button').disabled = false;
        }
    }
}

function toggleMR(id) {
    const box = document.getElementById('mr-box-' + id);
    const chk = document.getElementById('mr-chk-' + id);
    
    if (selectedMR.has(id)) {
        selectedMR.delete(id);
        box.classList.remove('selected');
        chk.checked = false;
    } else {
        selectedMR.add(id);
        box.classList.add('selected');
        chk.checked = true;
    }
    
    document.getElementById('answer_data').value = JSON.stringify({ choices: Array.from(selectedMR), timestamp: Date.now() });
    
    if (typeof IS_OPTIONAL !== 'undefined' && !IS_OPTIONAL) {
        document.getElementById('next-button').disabled = (selectedMR.size === 0);
    }
}

function setupFeedbackTask(currentQ, savedFeedback) {
    const feedbackPrompts = {
        21: "How do you feel about doing the spatial orientation questions?",
        22: "What do you think about doing the mental rotation questions?",
        23: "How would you like to improve our survey? Please provide suggestions and an overall rating out of 5.",
        24: "Did you experience any technical difficulties or confusion while taking this survey?",
        25: "Do you have any final thoughts or feedback you would like to share with the research team?"
    };
    
    document.getElementById('feedback-prompt').innerText = feedbackPrompts[currentQ];

    if (savedFeedback && savedFeedback.text) {
        document.getElementById('feedback-text').value = savedFeedback.text;
        document.getElementById('answer_data').value = JSON.stringify(savedFeedback);
        document.getElementById('next-button').disabled = false;
    }
}

function updateFeedback() {
    const text = document.getElementById('feedback-text').value;
    document.getElementById('answer_data').value = JSON.stringify({ text: text, timestamp: Date.now() });
    
    if (typeof IS_OPTIONAL !== 'undefined' && !IS_OPTIONAL) {
        document.getElementById('next-button').disabled = (text.trim().length === 0);
    }
}

function setupYNTask(currentQ, savedYN) {
    const ynPrompts = {
        26: "Have you ever taken a spatial reasoning or mental rotation test before?",
        27: "Do you regularly play 3D video games or use 3D modeling software?",
        28: "Do you find it generally easy to navigate a new city using a map?",
        29: "Did you feel rushed or anxious while completing the timed portions of this survey?",
        30: "Would you be willing to be contacted to participate in a follow-up study?"
    };
    
    document.getElementById('yn-prompt').innerText = ynPrompts[currentQ];
    
    if (savedYN && savedYN.choice) {
        selectYN(savedYN.choice);
    }
}

function selectYN(choice) {
    document.getElementById('yn-yes').classList.remove('selected');
    document.getElementById('yn-no').classList.remove('selected');
    
    if (choice === 'Yes') {
        document.getElementById('yn-yes').classList.add('selected');
    } else if (choice === 'No') {
        document.getElementById('yn-no').classList.add('selected');
    }
    
    document.getElementById('answer_data').value = JSON.stringify({ choice: choice, timestamp: Date.now() });
    document.getElementById('next-button').disabled = false;
}

function pickConsent(val) {
    document.getElementById('opt-yes').classList.remove('active');
    document.getElementById('opt-no').classList.remove('active');
    document.getElementById('opt-' + val).classList.add('active');
    
    document.getElementById('consent_given').value = val;
    
    const proceedBtn = document.getElementById('proceed-btn');
    const hint = document.getElementById('hint');
    
    if (val === 'yes') {
        hint.textContent = 'You have consented to participate.';
    } else {
        hint.textContent = 'You have declined consent. You may still proceed.';
    }
    
    proceedBtn.style.display = 'block';
}