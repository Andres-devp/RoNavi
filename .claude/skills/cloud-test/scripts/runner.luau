--!strict
-- cloud-test runner: executed by Open Cloud Luau Execution inside a real Roblox server.
--
-- cloud_test.py builds the game with an extra folder, ServerStorage.RoNaviCloudTests, that
-- mirrors the disk: tests/ (every *.spec.luau, also in subfolders such as tests/engine/) and
-- src/shared/, so a spec's `require("../src/shared/Core/X")` resolves exactly as under Lune.
-- A spec returns { [testName]: () -> () }; a test passes unless it errors (same contract
-- as the scaffold's `lune run test`). The place's own scripts do not run during the task.
--
-- Returns one JSON string; cloud_test.py reads it from the task output.

local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")

type Result = { spec: string, test: string, ok: boolean, err: string? }

local report = { passed = 0, failed = 0, results = {} :: { Result } }

local function record(spec: string, test: string, ok: boolean, err: string?)
	if ok then
		report.passed += 1
	else
		report.failed += 1
	end
	table.insert(report.results, { spec = spec, test = test, ok = ok, err = err })
end

local root = ServerStorage:FindFirstChild("RoNaviCloudTests")
local testsFolder = root and root:FindFirstChild("tests")
if not testsFolder then
	record(
		"(runner)",
		"RoNaviCloudTests/tests",
		false,
		"the uploaded place has no ServerStorage.RoNaviCloudTests.tests"
	)
	return HttpService:JSONEncode(report)
end

local specs: { ModuleScript } = {}
for _, inst in testsFolder:GetDescendants() do
	if inst:IsA("ModuleScript") and string.match(inst.Name, "%.spec$") then
		table.insert(specs, inst)
	end
end
table.sort(specs, function(a, b)
	return a:GetFullName() < b:GetFullName()
end)

local prefix = #testsFolder:GetFullName() + 2
for _, spec in specs do
	local name = string.sub(spec:GetFullName(), prefix)
	local loaded, tests = pcall(require, spec)
	if not loaded then
		record(name, "(could not load)", false, tostring(tests))
	elseif type(tests) ~= "table" then
		record(name, "(bad spec)", false, "a spec must return { [testName]: () -> () }")
	else
		local names: { string } = {}
		for testName in tests :: { [string]: any } do
			table.insert(names, testName)
		end
		table.sort(names)
		for _, testName in names do
			local ok, err = pcall((tests :: { [string]: () -> any })[testName])
			record(name, testName, ok, if ok then nil else tostring(err))
		end
	end
end

return HttpService:JSONEncode(report)
