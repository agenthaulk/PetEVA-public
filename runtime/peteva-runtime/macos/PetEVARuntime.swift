import AppKit
import Foundation

struct RuntimeConfig {
    let switchFile: String
    let framesDir: String
    let unitPrefix: String
    let scale: CGFloat
    let frameSeconds: TimeInterval
    let moveSeconds: TimeInterval
    let pollSeconds: TimeInterval
    let stepPixels: CGFloat
    let runStepPixels: CGFloat
    let jumpStepPixels: CGFloat
    let crawlStepPixels: CGFloat
    let jumpHeightScale: CGFloat
    let directionStrategy: String
    let stationaryChance: Double
    let horizontalChance: Double
    let verticalChance: Double
    let diagonalChance: Double
    let walkWeight: Double
    let runWeight: Double
    let crawlWeight: Double
    let jumpWeight: Double
    let verticalJumpWeight: Double
    let verticalWalkWeight: Double
    let screenMargin: CGFloat
    let minSegmentTicks: Int
    let maxSegmentTicks: Int
    let reminders: [ReminderConfig]
}

struct ReminderConfig {
    let id: String
    let enabled: Bool
    let intervalSeconds: TimeInterval
    let displaySeconds: TimeInterval
    let message: String
}

struct MovementStep {
    let dx: CGFloat
    let dy: CGFloat
    let rowName: String
    let movementKind: String
}

struct MotionPackRow {
    let actionName: String
    let mirror: Bool
}

final class PetView: NSView {
    var image: NSImage?
    var controls: NSStackView?
    var onShrink: (() -> Void)?
    var onGrow: (() -> Void)?
    var onClose: (() -> Void)?
    private var tracking: NSTrackingArea?
    private var dragOffset = NSPoint.zero
    private var reminderLabel: NSTextField?

    override var isOpaque: Bool { false }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = NSColor.clear.cgColor
        setupControls()
        setupReminderLabel()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not supported")
    }

    override func updateTrackingAreas() {
        if let tracking {
            removeTrackingArea(tracking)
        }
        tracking = NSTrackingArea(
            rect: bounds,
            options: [.activeAlways, .mouseEnteredAndExited, .inVisibleRect],
            owner: self,
            userInfo: nil
        )
        addTrackingArea(tracking!)
        super.updateTrackingAreas()
    }

    override func draw(_ dirtyRect: NSRect) {
        NSGraphicsContext.current?.cgContext.clear(bounds)
        image?.draw(in: bounds, from: .zero, operation: .sourceOver, fraction: 1.0)
    }

    override func mouseEntered(with event: NSEvent) {
        controls?.isHidden = false
    }

    override func mouseExited(with event: NSEvent) {
        controls?.isHidden = true
    }

    override func mouseDown(with event: NSEvent) {
        dragOffset = event.locationInWindow
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window else { return }
        let mouse = NSEvent.mouseLocation
        window.setFrameOrigin(NSPoint(x: mouse.x - dragOffset.x, y: mouse.y - dragOffset.y))
    }

    private func setupControls() {
        let stack = NSStackView()
        stack.orientation = .horizontal
        stack.spacing = 4
        stack.edgeInsets = NSEdgeInsets(top: 4, left: 4, bottom: 4, right: 4)
        stack.wantsLayer = true
        stack.layer?.backgroundColor = NSColor.black.withAlphaComponent(0.45).cgColor
        stack.layer?.cornerRadius = 6
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.isHidden = true

        for (title, action) in [("-", #selector(shrinkClicked)), ("+", #selector(growClicked)), ("x", #selector(closeClicked))] {
            let button = NSButton(title: title, target: self, action: action)
            button.isBordered = false
            button.bezelStyle = .regularSquare
            button.font = NSFont.systemFont(ofSize: 12, weight: .semibold)
            button.contentTintColor = .white
            button.translatesAutoresizingMaskIntoConstraints = false
            button.widthAnchor.constraint(equalToConstant: 22).isActive = true
            button.heightAnchor.constraint(equalToConstant: 20).isActive = true
            stack.addArrangedSubview(button)
        }

        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 6),
            stack.topAnchor.constraint(equalTo: topAnchor, constant: 6),
        ])
        controls = stack
    }

    private func setupReminderLabel() {
        let label = NSTextField(labelWithString: "")
        label.alignment = .center
        label.font = NSFont.systemFont(ofSize: 11, weight: .semibold)
        label.textColor = .white
        label.maximumNumberOfLines = 3
        label.lineBreakMode = .byWordWrapping
        label.wantsLayer = true
        label.layer?.backgroundColor = NSColor.black.withAlphaComponent(0.68).cgColor
        label.layer?.cornerRadius = 6
        label.translatesAutoresizingMaskIntoConstraints = false
        label.isHidden = true

        addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: centerXAnchor),
            label.topAnchor.constraint(equalTo: topAnchor, constant: 34),
            label.widthAnchor.constraint(lessThanOrEqualTo: widthAnchor, constant: -14),
        ])
        reminderLabel = label
    }

    func showReminder(_ message: String) {
        reminderLabel?.stringValue = message
        reminderLabel?.isHidden = false
    }

    func hideReminder() {
        reminderLabel?.isHidden = true
    }

    @objc private func shrinkClicked() {
        onShrink?()
    }

    @objc private func growClicked() {
        onGrow?()
    }

    @objc private func closeClicked() {
        onClose?()
    }
}

final class PetRuntime: NSObject, NSApplicationDelegate {
    private let config: RuntimeConfig
    private var window: NSWindow!
    private var petView: PetView!
    private var framesByRow: [String: [NSImage]] = [:]
    private var currentRowName = "idle"
    private var frameIndex = 0
    private var scale: CGFloat
    private var currentStep = MovementStep(dx: 0, dy: 0, rowName: "idle", movementKind: "idle")
    private var movementTicksRemaining = 0
    private var movementPhase = 0
    private var renderedFramePhase = 0
    private var waitingForSegmentFrame = false
    private var frameTimer: Timer?
    private var movementTimer: Timer?
    private var pollTimer: Timer?
    private var reminderTimers: [Timer] = []
    private var reminderHideTimer: Timer?
    private var motionPackFolder: String {
        "2026-05-13-\(config.unitPrefix)-motion-12frame/runtime-12frame-clean"
    }
    private let motionPackFrameCount = 12
    private let motionPackRows: [String: MotionPackRow] = [
        "walking-right": MotionPackRow(actionName: "walking", mirror: true),
        "walking-left": MotionPackRow(actionName: "walking", mirror: false),
        "running-right": MotionPackRow(actionName: "running", mirror: true),
        "running-left": MotionPackRow(actionName: "running", mirror: false),
        "crawling-right": MotionPackRow(actionName: "crawling", mirror: true),
        "crawling-left": MotionPackRow(actionName: "crawling", mirror: false),
        "jumping": MotionPackRow(actionName: "vertical-jump", mirror: false),
        "jumping-right": MotionPackRow(actionName: "diagonal-jump-right", mirror: false),
        "jumping-left": MotionPackRow(actionName: "diagonal-jump", mirror: false),
    ]

    init(config: RuntimeConfig) {
        self.config = config
        self.scale = config.scale
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard isEnabled() else {
            print("PetEVA runtime stopped: local switch disabled")
            NSApp.terminate(nil)
            return
        }
        do {
            framesByRow = try loadFrames()
            createWindow()
            startTimers()
        } catch {
            fputs("PetEVA runtime error: \(error)\n", stderr)
            NSApp.terminate(nil)
        }
    }

    private func createWindow() {
        let size = windowSize()
        let origin = initialOrigin(size: size)
        petView = PetView(frame: NSRect(origin: .zero, size: size))
        petView.image = framesByRow["idle"]?.first
        petView.onShrink = { [weak self] in self?.setScale(max(0.45, (self?.scale ?? 0.75) - 0.1)) }
        petView.onGrow = { [weak self] in self?.setScale(min(1.25, (self?.scale ?? 0.75) + 0.1)) }
        petView.onClose = { NSApp.terminate(nil) }

        window = NSWindow(
            contentRect: NSRect(origin: origin, size: size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.ignoresMouseEvents = false
        window.contentView = petView
        window.orderFrontRegardless()
    }

    private func startTimers() {
        frameTimer = Timer.scheduledTimer(withTimeInterval: config.frameSeconds, repeats: true) { [weak self] _ in
            self?.tickFrame()
        }
        movementTimer = Timer.scheduledTimer(withTimeInterval: config.moveSeconds, repeats: true) { [weak self] _ in
            self?.tickMovement()
        }
        pollTimer = Timer.scheduledTimer(withTimeInterval: config.pollSeconds, repeats: true) { [weak self] _ in
            guard let self else { return }
            if !self.isEnabled() {
                print("PetEVA runtime stopped: local switch disabled")
                NSApp.terminate(nil)
            }
        }
        startReminderTimers()
    }

    private func startReminderTimers() {
        for reminder in config.reminders where reminder.enabled {
            let timer = Timer.scheduledTimer(withTimeInterval: reminder.intervalSeconds, repeats: true) { [weak self] _ in
                self?.showReminder(reminder)
            }
            reminderTimers.append(timer)
        }
    }

    private func showReminder(_ reminder: ReminderConfig) {
        petView.showReminder(reminder.message)
        reminderHideTimer?.invalidate()
        reminderHideTimer = Timer.scheduledTimer(withTimeInterval: min(reminder.displaySeconds, 60), repeats: false) { [weak self] _ in
            self?.petView.hideReminder()
        }
    }

    private func tickFrame() {
        let frames = framesByRow[currentRowName] ?? framesByRow["idle"] ?? []
        guard !frames.isEmpty else { return }
        let phase = frameIndex % frames.count
        petView.image = frames[phase]
        petView.needsDisplay = true
        renderedFramePhase = phase
        if waitingForSegmentFrame {
            waitingForSegmentFrame = false
        }
        frameIndex = (phase + 1) % frames.count
    }

    private func tickMovement() {
        if movementTicksRemaining <= 0 {
            currentStep = redirectStepAwayFromEdges(chooseMovementStep())
            currentRowName = currentStep.rowName
            frameIndex = 0
            renderedFramePhase = 0
            waitingForSegmentFrame = true
            movementTicksRemaining = segmentTickCount(for: currentStep)
        }
        if !waitingForSegmentFrame {
            movementPhase = renderedFramePhase
            let frameCount = framesByRow[currentRowName]?.count ?? 8
            let delta = movementDeltaForPhase(
                currentStep,
                phase: movementPhase,
                frameCount: frameCount,
                jumpHeightPixels: window.frame.height * config.jumpHeightScale
            )
            if delta.dx != 0 || delta.dy != 0 {
                moveBy(dx: delta.dx, dy: delta.dy)
            }
            movementTicksRemaining -= 1
        }
    }

    private func segmentTickCount(for step: MovementStep) -> Int {
        if step.movementKind == "jump" {
            return framesByRow[step.rowName]?.count ?? motionPackFrameCount
        }
        return Int.random(in: config.minSegmentTicks...config.maxSegmentTicks)
    }

    private func chooseMovementStep() -> MovementStep {
        if Double.random(in: 0..<1) < config.stationaryChance {
            return MovementStep(dx: 0, dy: 0, rowName: "idle", movementKind: "idle")
        }

        if config.directionStrategy == "legacyWeighted" {
            return chooseLegacyWeightedMovementStep()
        }
        return chooseUniformMovementStep()
    }

    private func chooseUniformMovementStep() -> MovementStep {
        let horizontalPrimary = Double.random(in: 0..<1) < horizontalPrimaryChance()
        let movementKind = chooseUniformMovementKind(horizontalPrimary: horizontalPrimary)
        let stepPixels = uniformStepPixels(maxPixels: stepPixelsForKind(movementKind))
        let direction = uniformDirection(horizontalPrimary: movementKind != "jump")
        let dx = direction.dx * stepPixels
        let dy = direction.dy * stepPixels
        return MovementStep(dx: dx, dy: dy, rowName: rowName(dx: dx, dy: dy, movementKind: movementKind), movementKind: movementKind)
    }

    private func chooseLegacyWeightedMovementStep() -> MovementStep {
        let horizontalPrimary = Double.random(in: 0..<1) < horizontalPrimaryChance()
        let diagonal = Double.random(in: 0..<1) < config.diagonalChance
        let verticalCandidate = !horizontalPrimary || diagonal
        let verticalJump = verticalCandidate && chooseVerticalJump()
        let movementKind = verticalJump ? "jump" : chooseMovementKind(includeJump: false)
        let stepPixels = stepPixelsForKind(movementKind)
        var dx: CGFloat = 0
        var dy: CGFloat = 0
        if horizontalPrimary {
            dx = signedStep(stepPixels)
            if diagonal && verticalJump {
                dy = signedStep(stepPixels)
            }
        } else {
            if verticalJump {
                dy = signedStep(stepPixels)
            } else {
                dx = signedStep(config.stepPixels)
            }
            if diagonal && verticalJump {
                dx = signedStep(stepPixels)
            }
        }
        return MovementStep(dx: dx, dy: dy, rowName: rowName(dx: dx, dy: dy, movementKind: movementKind), movementKind: movementKind)
    }

    private func horizontalPrimaryChance() -> Double {
        let total = config.horizontalChance + config.verticalChance
        if total <= 0 { return 1 }
        return config.horizontalChance / total
    }

    private func rowName(dx: CGFloat, dy: CGFloat, movementKind: String) -> String {
        if movementKind == "jump" {
            if dx > 0 && dy != 0 { return "jumping-right" }
            if dx < 0 && dy != 0 { return "jumping-left" }
            return "jumping"
        }
        if dx > 0 {
            if movementKind == "crawl" { return "crawling-right" }
            return movementKind == "run" ? "running-right" : "walking-right"
        }
        if dx < 0 {
            if movementKind == "crawl" { return "crawling-left" }
            return movementKind == "run" ? "running-left" : "walking-left"
        }
        if dy != 0 { return "jumping" }
        return "idle"
    }

    private func chooseMovementKind(includeJump: Bool) -> String {
        var options = [
            ("walk", config.walkWeight),
            ("run", config.runWeight),
            ("crawl", config.crawlWeight),
        ]
        if includeJump {
            options.append(("jump", config.jumpWeight))
        }
        return weightedKind(options)
    }

    private func chooseUniformMovementKind(horizontalPrimary: Bool) -> String {
        if horizontalPrimary {
            if groundWeightTotal() > 0 {
                return chooseMovementKind(includeJump: false)
            }
            return "jump"
        }
        if config.jumpWeight > 0 {
            return "jump"
        }
        return chooseMovementKind(includeJump: false)
    }

    private func groundWeightTotal() -> Double {
        max(0.0, config.walkWeight) + max(0.0, config.runWeight) + max(0.0, config.crawlWeight)
    }

    private func chooseVerticalJump() -> Bool {
        weightedKind([
            ("jump", config.verticalJumpWeight),
            ("walk", config.verticalWalkWeight),
        ]) == "jump"
    }

    private func weightedKind(_ options: [(String, Double)]) -> String {
        let total = options.reduce(0.0) { $0 + max(0.0, $1.1) }
        if total <= 0 { return options.first?.0 ?? "walk" }
        let roll = Double.random(in: 0..<total)
        var cursor = 0.0
        for (name, weight) in options {
            cursor += max(0.0, weight)
            if roll < cursor {
                return name
            }
        }
        return options.last?.0 ?? "walk"
    }

    private func stepPixelsForKind(_ movementKind: String) -> CGFloat {
        if movementKind == "run" { return config.runStepPixels }
        if movementKind == "jump" { return config.jumpStepPixels }
        if movementKind == "crawl" { return config.crawlStepPixels }
        return config.stepPixels
    }

    private func signedStep(_ stepPixels: CGFloat) -> CGFloat {
        Bool.random() ? stepPixels : -stepPixels
    }

    private func uniformStepPixels(maxPixels: CGFloat) -> CGFloat {
        let lower = max(1.0, ceil(maxPixels * 0.7))
        return CGFloat.random(in: lower...maxPixels)
    }

    private func uniformDirection(horizontalPrimary: Bool) -> (dx: CGFloat, dy: CGFloat) {
        let directions: [(CGFloat, CGFloat)] = horizontalPrimary
            ? [(-1, 0), (1, 0)]
            : [(0, -1), (0, 1)]
        return directions.randomElement() ?? (1, 0)
    }

    private func movementDeltaForPhase(
        _ step: MovementStep,
        phase: Int,
        frameCount: Int,
        jumpHeightPixels: CGFloat
    ) -> (dx: CGFloat, dy: CGFloat) {
        if step.dx == 0 && step.dy == 0 {
            return (0, 0)
        }

        let normalizedPhase = phase % max(frameCount, 1)
        if step.movementKind == "jump" && jumpHeightPixels > 0 {
            let phases = propulsivePhases("jump", frameCount: frameCount)
            let dx = phases.contains(normalizedPhase) ? step.dx : 0
            let dy = jumpArcDelta(
                phase: normalizedPhase,
                frameCount: frameCount,
                jumpHeightPixels: jumpHeightPixels
            )
            return (dx, dy)
        }
        return phaseDelta(step, normalizedPhase, propulsivePhases(step.movementKind, frameCount: frameCount))
    }

    private func propulsivePhases(_ movementKind: String, frameCount: Int) -> Set<Int> {
        if frameCount <= 1 { return [0] }
        let lastPhase = frameCount - 1
        if movementKind == "jump" {
            return Set(1..<lastPhase)
        }
        if movementKind == "run" {
            return Set((0..<frameCount).filter { $0 % 3 != 2 })
        }
        if movementKind == "crawl" {
            return Set(1..<lastPhase)
        }
        return Set((0..<frameCount).filter { $0 % 2 == 1 })
    }

    private func phaseDelta(_ step: MovementStep, _ phase: Int, _ propulsivePhases: Set<Int>) -> (dx: CGFloat, dy: CGFloat) {
        if propulsivePhases.contains(phase) {
            return (step.dx, step.dy)
        }
        return (0, 0)
    }

    private func jumpArcDelta(phase: Int, frameCount: Int, jumpHeightPixels: CGFloat) -> CGFloat {
        if frameCount <= 1 { return 0 }
        let previousPhase = phase > 0 ? phase - 1 : frameCount - 1
        return jumpArcOffset(phase: phase, frameCount: frameCount, jumpHeightPixels: jumpHeightPixels)
            - jumpArcOffset(phase: previousPhase, frameCount: frameCount, jumpHeightPixels: jumpHeightPixels)
    }

    private func jumpArcOffset(phase: Int, frameCount: Int, jumpHeightPixels: CGFloat) -> CGFloat {
        if frameCount <= 1 { return 0 }
        let progress = CGFloat(phase) / CGFloat(frameCount - 1)
        return -round(jumpHeightPixels * sin(CGFloat.pi * progress))
    }

    private func redirectStepAwayFromEdges(_ step: MovementStep) -> MovementStep {
        var dx = step.dx
        var dy = step.dy
        let visible = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        let frame = window.frame
        let minX = visible.minX + config.screenMargin
        let maxX = visible.maxX - frame.width - config.screenMargin
        let minY = visible.minY + config.screenMargin
        let maxY = visible.maxY - frame.height - config.screenMargin

        if frame.origin.x <= minX && dx < 0 {
            dx = abs(dx)
        } else if frame.origin.x >= maxX && dx > 0 {
            dx = -abs(dx)
        }

        if frame.origin.y <= minY && dy > 0 {
            dy = -abs(dy)
        } else if frame.origin.y >= maxY && dy < 0 {
            dy = abs(dy)
        }

        if dx == step.dx && dy == step.dy {
            return step
        }
        return MovementStep(dx: dx, dy: dy, rowName: rowName(dx: dx, dy: dy, movementKind: step.movementKind), movementKind: step.movementKind)
    }

    private func moveBy(dx: CGFloat, dy: CGFloat) {
        var frame = window.frame
        frame.origin.x += dx
        frame.origin.y -= dy
        frame.origin = clampedOrigin(for: frame)
        window.setFrameOrigin(frame.origin)
    }

    private func setScale(_ newScale: CGFloat) {
        scale = newScale
        let oldFrame = window.frame
        let size = windowSize()
        let origin = clampedOrigin(for: NSRect(origin: oldFrame.origin, size: size))
        window.setFrame(NSRect(origin: origin, size: size), display: true)
        petView.frame = NSRect(origin: .zero, size: size)
        petView.needsDisplay = true
    }

    private func windowSize() -> NSSize {
        let frame = framesByRow["idle"]?.first
        return NSSize(width: (frame?.size.width ?? 192) * scale, height: (frame?.size.height ?? 208) * scale)
    }

    private func initialOrigin(size: NSSize) -> NSPoint {
        let visible = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        let minX = visible.minX + config.screenMargin
        let maxX = max(minX, visible.maxX - size.width - config.screenMargin)
        let minY = visible.minY + config.screenMargin
        let maxY = max(minY, visible.maxY - size.height - config.screenMargin)
        return NSPoint(
            x: CGFloat.random(in: minX...maxX),
            y: CGFloat.random(in: minY...maxY)
        )
    }

    private func clampedOrigin(for frame: NSRect) -> NSPoint {
        let visible = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        let minX = visible.minX + config.screenMargin
        let maxX = visible.maxX - frame.width - config.screenMargin
        let minY = visible.minY + config.screenMargin
        let maxY = visible.maxY - frame.height - config.screenMargin
        return NSPoint(
            x: min(max(frame.origin.x, minX), maxX),
            y: min(max(frame.origin.y, minY), maxY)
        )
    }

    private func loadFrames() throws -> [String: [NSImage]] {
        var rows: [String: [NSImage]] = [:]
        rows["idle"] = try loadTopLevelRow("idle", count: 8)
        rows["walking-right"] = loadMotionPackRow("walking-right") ?? rows["idle"]!
        rows["walking-left"] = loadMotionPackRow("walking-left") ?? rows["walking-right"]!
        rows["running-right"] = loadMotionPackRow("running-right") ?? rows["walking-right"]!
        rows["running-left"] = loadMotionPackRow("running-left") ?? rows["walking-left"]!
        rows["crawling-right"] = loadMotionPackRow("crawling-right") ?? rows["walking-right"]!
        rows["crawling-left"] = loadMotionPackRow("crawling-left") ?? rows["walking-left"]!
        rows["jumping"] = loadMotionPackRow("jumping") ?? rows["idle"]!
        rows["jumping-right"] = loadMotionPackRow("jumping-right") ?? rows["jumping"]!
        rows["jumping-left"] = loadMotionPackRow("jumping-left") ?? rows["jumping"]!
        return rows
    }

    private func loadTopLevelRow(_ rowName: String, count: Int) throws -> [NSImage] {
        var frames: [NSImage] = []
        for index in 0..<count {
            let path = "\(config.framesDir)/\(config.unitPrefix)-\(rowName)-\(String(format: "%02d", index)).png"
            guard let image = NSImage(contentsOfFile: path) else {
                throw RuntimeError("missing frame: \(path)")
            }
            frames.append(image)
        }
        return frames
    }

    private func loadMotionPackRow(_ rowName: String) -> [NSImage]? {
        guard let motionPackRow = motionPackRows[rowName] else { return nil }
        var frames: [NSImage] = []
        for index in 1...motionPackFrameCount {
            let path = "\(config.framesDir)/\(motionPackFolder)/\(motionPackRow.actionName)/frame-\(String(format: "%02d", index)).png"
            guard let image = NSImage(contentsOfFile: path) else {
                return nil
            }
            frames.append(motionPackRow.mirror ? mirrored(image) : image)
        }
        return frames
    }

    private func mirrored(_ image: NSImage) -> NSImage {
        let mirroredImage = NSImage(size: image.size)
        mirroredImage.lockFocus()
        let transform = NSAffineTransform()
        transform.translateX(by: image.size.width, yBy: 0)
        transform.scaleX(by: -1, yBy: 1)
        transform.concat()
        image.draw(at: .zero, from: NSRect(origin: .zero, size: image.size), operation: .sourceOver, fraction: 1.0)
        mirroredImage.unlockFocus()
        return mirroredImage
    }

    private func isEnabled() -> Bool {
        guard let data = FileManager.default.contents(atPath: config.switchFile),
              let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return false
        }
        return payload["enabled"] as? Bool ?? false
    }
}

struct RuntimeError: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) {
        self.description = description
    }
}

func parseConfig() -> RuntimeConfig {
    var switchFile = ""
    var framesDir = ""
    var unitPrefix = "unit01"
    var scale: CGFloat = 0.75
    var frameMS = 120.0
    var moveMS = 120.0
    var pollMS = 500.0
    var stepPixels: CGFloat = 8
    var runStepPixels: CGFloat = 14
    var jumpStepPixels: CGFloat = 12
    var crawlStepPixels: CGFloat = 6
    var jumpHeightScale: CGFloat = 1.2
    var directionStrategy = "uniform"
    var stationaryChance = 0.7
    var horizontalChance = 0.1
    var verticalChance = 0.9
    var diagonalChance = 0.2
    var walkWeight = 6.0
    var runWeight = 1.0
    var crawlWeight = 1.0
    var jumpWeight = 2.0
    var verticalJumpWeight = 1.0
    var verticalWalkWeight = 4.0
    var screenMargin: CGFloat = 8
    var minSegmentTicks = 8
    var maxSegmentTicks = 20
    var waterReminderEnabled = true
    var waterReminderIntervalMinutes = 20
    var waterReminderDisplaySeconds = 55
    var waterReminderMessage = "Time to drink water."
    var activityReminderEnabled = true
    var activityReminderIntervalMinutes = 30
    var activityReminderDisplaySeconds = 55
    var activityReminderMessage = "Time to stand up and move."

    var args = Array(CommandLine.arguments.dropFirst())
    while !args.isEmpty {
        let key = args.removeFirst()
        guard !args.isEmpty else { break }
        let value = args.removeFirst()
        switch key {
        case "--switch-file":
            switchFile = value
        case "--frames-dir":
            framesDir = value
        case "--unit-prefix":
            unitPrefix = value
        case "--scale":
            scale = CGFloat(Double(value) ?? 0.75)
        case "--frame-ms":
            frameMS = Double(value) ?? 120.0
        case "--move-ms":
            moveMS = Double(value) ?? 120.0
        case "--poll-ms":
            pollMS = Double(value) ?? 500.0
        case "--step-pixels":
            stepPixels = CGFloat(Double(value) ?? 8.0)
        case "--run-step-pixels":
            runStepPixels = CGFloat(Double(value) ?? 14.0)
        case "--jump-step-pixels":
            jumpStepPixels = CGFloat(Double(value) ?? 12.0)
        case "--crawl-step-pixels":
            crawlStepPixels = CGFloat(Double(value) ?? 6.0)
        case "--jump-height-scale":
            jumpHeightScale = CGFloat(Double(value) ?? 1.2)
        case "--direction-strategy":
            directionStrategy = value
        case "--stationary-chance":
            stationaryChance = Double(value) ?? 0.7
        case "--horizontal-chance":
            horizontalChance = Double(value) ?? 0.1
        case "--vertical-chance":
            verticalChance = Double(value) ?? 0.9
        case "--diagonal-chance":
            diagonalChance = Double(value) ?? 0.2
        case "--walk-weight":
            walkWeight = Double(value) ?? 6.0
        case "--run-weight":
            runWeight = Double(value) ?? 1.0
        case "--crawl-weight":
            crawlWeight = Double(value) ?? 1.0
        case "--jump-weight":
            jumpWeight = Double(value) ?? 2.0
        case "--vertical-jump-weight":
            verticalJumpWeight = Double(value) ?? 1.0
        case "--vertical-walk-weight":
            verticalWalkWeight = Double(value) ?? 4.0
        case "--screen-margin":
            screenMargin = CGFloat(Double(value) ?? 8.0)
        case "--min-segment-ticks":
            minSegmentTicks = Int(value) ?? 8
        case "--max-segment-ticks":
            maxSegmentTicks = Int(value) ?? 20
        case "--water-reminder-enabled":
            waterReminderEnabled = value == "true"
        case "--water-reminder-interval-minutes":
            waterReminderIntervalMinutes = Int(value) ?? 20
        case "--water-reminder-display-seconds":
            waterReminderDisplaySeconds = min(Int(value) ?? 55, 60)
        case "--water-reminder-message":
            waterReminderMessage = value
        case "--activity-reminder-enabled":
            activityReminderEnabled = value == "true"
        case "--activity-reminder-interval-minutes":
            activityReminderIntervalMinutes = Int(value) ?? 30
        case "--activity-reminder-display-seconds":
            activityReminderDisplaySeconds = min(Int(value) ?? 55, 60)
        case "--activity-reminder-message":
            activityReminderMessage = value
        default:
            break
        }
    }

    if maxSegmentTicks < minSegmentTicks {
        maxSegmentTicks = minSegmentTicks
    }

    return RuntimeConfig(
        switchFile: switchFile,
        framesDir: framesDir,
        unitPrefix: unitPrefix,
        scale: scale,
        frameSeconds: frameMS / 1000.0,
        moveSeconds: moveMS / 1000.0,
        pollSeconds: pollMS / 1000.0,
        stepPixels: stepPixels,
        runStepPixels: runStepPixels,
        jumpStepPixels: jumpStepPixels,
        crawlStepPixels: crawlStepPixels,
        jumpHeightScale: jumpHeightScale,
        directionStrategy: directionStrategy,
        stationaryChance: stationaryChance,
        horizontalChance: horizontalChance,
        verticalChance: verticalChance,
        diagonalChance: diagonalChance,
        walkWeight: walkWeight,
        runWeight: runWeight,
        crawlWeight: crawlWeight,
        jumpWeight: jumpWeight,
        verticalJumpWeight: verticalJumpWeight,
        verticalWalkWeight: verticalWalkWeight,
        screenMargin: screenMargin,
        minSegmentTicks: minSegmentTicks,
        maxSegmentTicks: maxSegmentTicks,
        reminders: [
            ReminderConfig(
                id: "water",
                enabled: waterReminderEnabled,
                intervalSeconds: TimeInterval(waterReminderIntervalMinutes * 60),
                displaySeconds: TimeInterval(waterReminderDisplaySeconds),
                message: waterReminderMessage
            ),
            ReminderConfig(
                id: "activity",
                enabled: activityReminderEnabled,
                intervalSeconds: TimeInterval(activityReminderIntervalMinutes * 60),
                displaySeconds: TimeInterval(activityReminderDisplaySeconds),
                message: activityReminderMessage
            ),
        ]
    )
}

let config = parseConfig()
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = PetRuntime(config: config)
app.delegate = delegate
app.run()
